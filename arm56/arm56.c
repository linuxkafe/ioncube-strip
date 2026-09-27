/*
  +----------------------------------------------------------------------+
  | ioncube-strip — arm56 v4 (E1 spike)                                 |
  +----------------------------------------------------------------------+
  | Serializes the zend_op_array that the ionCube Loader materializes   |
  | for an encoded file into JSON. The loader patches zend_compile_file  |
  | at startup; this extension is loaded AFTER the loader, so it wraps  |
  | the loader's compile entry point rather than replacing it.          |
  |                                                                      |
  | Output directory comes from the ARM56_JSON environment variable.    |
  | When unset the extension is a no-op.                                 |
  |                                                                      |
  | SPDX-License-Identifier: MIT                                         |
  +----------------------------------------------------------------------+
*/

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "php.h"
#include "php_ini.h"
#include "ext/standard/info.h"
#include "Zend/zend_compile.h"
#include "Zend/zend_vm_opcodes.h"
#include "Zend/zend_exceptions.h"
#include "Zend/zend_hash.h"

#include <signal.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ARM56_VERSION "4.0.0-spike"

/* Highest opcode defined by the stock PHP 5.6 VM (ZEND_ASSIGN_POW). Anything
 * above this in an encoded file comes from the loader's own instruction set
 * and has no zend_get_opcode_name() entry. PHP 5.6 exports no ZEND_VM_LAST_OPCODE. */
#define ZEND_STANDARD_OPCODE_MAX 167

/* The loader frees or corrupts some literal buckets mid-walk. A fault
 * inside a single op_array must not abort the whole dump. */
static sigjmp_buf arm56_jump;
static char arm56_altstack[65536];
static volatile sig_atomic_t arm56_faulted;
static void arm56_fault_handler(int sig)
{
	(void)sig;
	arm56_faulted = 1;
	siglongjmp(arm56_jump, 1);
}

static zend_op_array *(*arm56_orig_compile_file)(zend_file_handle *, int TSRMLS_DC);

/* Read on demand: memory allocated during MINIT belongs to the request
 * arena and is not valid for the lifetime of the extension. */
static const char *arm56_outdir(void)
{
	char *env = getenv("ARM56_JSON");
	return (env && *env) ? env : NULL;
}

/* ------------------------------------------------------------------ */
/* JSON emission                                                       */
/* ------------------------------------------------------------------ */

static void json_escape(FILE *f, const char *s, size_t len)
{
	size_t i;
	for (i = 0; i < len; i++) {
		unsigned char c = (unsigned char)s[i];
		switch (c) {
			case '"':  fputs("\\\"", f); break;
			case '\\': fputs("\\\\", f); break;
			case '\n': fputs("\\n", f);  break;
			case '\r': fputs("\\r", f);  break;
			case '\t': fputs("\\t", f);  break;
			case '\b': fputs("\\b", f);  break;
			case '\f': fputs("\\f", f);  break;
			default:
				/* Bytes >= 0x80 are escaped individually. Passing them
				 * through would emit invalid UTF-8 and the whole
				 * document would fail to parse. Literal pools are
				 * effectively ASCII, so nothing legible is lost. */
				if (c < 0x20 || c >= 0x7f) {
					fprintf(f, "\\u%04x", c);
				} else {
					fputc(c, f);
				}
		}
	}
}

/* ------------------------------------------------------------------ */
/* JSON emission                                                       */
/*                                                                     */
/* A per-object "first key written" stack, because the separator comma */
/* belongs to the object being written, not to the function emitting.  */
/* ------------------------------------------------------------------ */

#define JSON_MAX_DEPTH 32
static int json_fresh[JSON_MAX_DEPTH];
static int json_depth = -1;

static void jobj_open(FILE *f, char open)
{
	if (json_depth + 1 < JSON_MAX_DEPTH) {
		json_depth++;
		json_fresh[json_depth] = 1;
	}
	fputc(open, f);
}

static void jobj_close(FILE *f, char close)
{
	if (json_depth >= 0) { json_depth--; }
	fputc(close, f);
}

static void json_key(FILE *f, const char *k)
{
	if (json_depth >= 0 && !json_fresh[json_depth]) { fputc(',', f); }
	if (json_depth >= 0) { json_fresh[json_depth] = 0; }
	fputc('"', f);
	fputs(k, f);
	fputs("\":", f);
}

static void json_str(FILE *f, const char *k, const char *v)
{
	if (!v) { json_key(f, k); fputs("null", f); return; }
	json_key(f, k); fputc('"', f); json_escape(f, v, strlen(v)); fputc('"', f);
}

/* Emits a bare quoted string, for the one place a value is written outside
 * the object helpers (the fault placeholder). */
static void json_strval(FILE *f, const char *v)
{
	if (!v) { fputs("null", f); return; }
	fputc('"', f);
	json_escape(f, v, strlen(v));
	fputc('"', f);
}

static void json_int(FILE *f, const char *k, long long v)
{
	json_key(f, k); fprintf(f, "%lld", v);
}

static void json_bool(FILE *f, const char *k, int v)
{
	json_key(f, k); fputs(v ? "true" : "false", f);
}

/* Renders one operand. Type is derived from the compiled operand kind; the
 * value is an index for CV/TMP/VAR, a string for string literals, a number
 * for numeric literals, and a raw pointer for control-flow targets. */
static void json_operand(FILE *f, const char *k, zend_op_array *oa,
                         const zend_op *op, int which)
{
	zend_uchar type;
	const znode_op *node;

	if (which == 1) { type = op->op1_type; node = &op->op1; }
	else            { type = op->op2_type; node = &op->op2; }

	json_key(f, k);

	if (type == IS_UNUSED) {
		fputs("null", f);
	} else if (type == IS_CV || type == IS_VAR || type == IS_TMP_VAR) {
		fprintf(f, "%u", (unsigned)node->var);
	} else if (type == IS_CONST) {
		zend_literal *lit = node->literal;
		if (!lit) {
			fputs("null", f);
		} else if (Z_TYPE(lit->constant) == IS_STRING) {
			fputc('"', f);
			json_escape(f, Z_STRVAL(lit->constant), Z_STRLEN(lit->constant));
			fputc('"', f);
		} else if (Z_TYPE(lit->constant) == IS_NULL) {
			fputs("null", f);
		} else if (Z_TYPE(lit->constant) == IS_LONG || Z_TYPE(lit->constant) == IS_DOUBLE) {
			char buf[64];
			int n;
			if (Z_TYPE(lit->constant) == IS_LONG) {
				n = snprintf(buf, sizeof(buf), "%ld", Z_LVAL(lit->constant));
			} else {
				n = snprintf(buf, sizeof(buf), "%.17g", Z_DVAL(lit->constant));
			}
			if (n > 0) { fwrite(buf, 1, (size_t)n, f); } else { fputs("0", f); }
		} else if (Z_TYPE(lit->constant) == IS_CONSTANT_AST) {
			fputs("\"<ast>\"", f);
		} else {
			/* bool, array, null-as-empty, objects folded at compile time */
			fputc('"', f);
			json_escape(f, zend_get_type_by_const(Z_TYPE(lit->constant)), strlen(zend_get_type_by_const(Z_TYPE(lit->constant))));
			fputc('"', f);
		}
	} else {
		/* control-flow operand: emit target opline index */
		if (node->jmp_addr && oa->opcodes) {
			fprintf(f, "%ld", (long)(node->jmp_addr - oa->opcodes));
		} else {
			fputs("null", f);
		}
	}
}

/* ------------------------------------------------------------------ */
/* op_array traversal                                                  */
/* ------------------------------------------------------------------ */

/* op_array->scope is a zend_class_entry*, and class entries are not reliably
 * readable in this build (T028). The owning class name is therefore supplied
 * by the caller, which already has it from zend_lookup_class. */
static const char *arm56_scope_override;

static const char *scope_name(zend_op_array *oa)
{
	(void)oa;
	return arm56_scope_override;
}

static const char *kind_of(zend_op_array *oa, int is_main)
{
	/* A method is the only kind of op_array that carries a scope. PHP 5.6
	 * exposes no ZEND_ACC_METHOD flag, so scope presence is the test. */
	if (is_main) { return "main"; }
	if (arm56_scope_override) { return "method"; }
	return "function";
}

static void dump_meta(FILE *f, zend_op_array *oa, int is_main, const char *via,
                  int depth)
{
	zend_uint i;
	int first;

	if (depth > 12) { fputs("null", f); return; }

	jobj_open(f, '{');
	if (via) { json_str(f, "via", via); }
	json_str(f, "kind", kind_of(oa, is_main));
	json_str(f, "name", oa->function_name);
	json_str(f, "scope", scope_name(oa));
	json_str(f, "filename", oa->filename);
	json_int(f, "line_start", (long long)oa->line_start);
	json_int(f, "line_end", (long long)oa->line_end);
	json_int(f, "num_args", (long long)oa->num_args);
	json_int(f, "required_num_args", (long long)oa->required_num_args);
	json_int(f, "fn_flags", (long long)oa->fn_flags);
	json_bool(f, "is_static", (oa->fn_flags & ZEND_ACC_STATIC) != 0);
	json_bool(f, "is_abstract", (oa->fn_flags & ZEND_ACC_ABSTRACT) != 0);
	json_bool(f, "is_public", (oa->fn_flags & ZEND_ACC_PUBLIC) != 0);
	json_bool(f, "is_protected", (oa->fn_flags & ZEND_ACC_PROTECTED) != 0);
	json_bool(f, "is_private", (oa->fn_flags & ZEND_ACC_PRIVATE) != 0);
	json_int(f, "num_ops", (long long)oa->last);
	json_int(f, "num_vars", (long long)oa->last_var);
	json_int(f, "num_literals", (long long)oa->last_literal);

	if (oa->doc_comment) {
		json_key(f, "doc_comment");
		fputc('"', f);
		json_escape(f, oa->doc_comment, oa->doc_comment_len);
		fputc('"', f);
	} else {
		json_str(f, "doc_comment", NULL);
	}

	/* argument names */
	json_key(f, "args");
	fputc('[', f);
	for (i = 0; i < oa->num_args; i++) {
		if (i) { fputc(',', f); }
		jobj_open(f, '{');
		json_str(f, "name", oa->arg_info && oa->arg_info[i].name
		                 ? oa->arg_info[i].name : NULL);
		json_int(f, "type_hint", (long long)oa->arg_info[i].type_hint);
		json_str(f, "class_name", oa->arg_info && oa->arg_info[i].class_name
		                    ? oa->arg_info[i].class_name : NULL);
		json_bool(f, "pass_by_ref", oa->arg_info[i].pass_by_reference != 0);
		json_bool(f, "allow_null", oa->arg_info[i].allow_null != 0);
		json_bool(f, "is_variadic", oa->arg_info[i].is_variadic != 0);
		jobj_close(f, '}');
	}
	fputc(']', f);

	/* compiled variables */
	json_key(f, "vars");
	fputc('[', f);
	for (i = 0; i < (zend_uint)oa->last_var; i++) {
		if (i) { fputc(',', f); }
		fputc('"', f);
		json_escape(f, oa->vars[i].name, (size_t)oa->vars[i].name_len);
		fputc('"', f);
	}
	fputc(']', f);
}

/* Literal pool and opcode stream. Split out from dump_meta so it can be
 * discarded independently: for encoded files the loader keeps this encrypted
 * until the body executes, and reading it faults. */
static void dump_content(FILE *f, zend_op_array *oa)
{
	zend_uint i;
	int first;

	if (!oa) { return; }

	if (!oa->literals || !oa->opcodes) { return; }

	/* literals */
	json_key(f, "literals");
	fputc('[', f);
	for (i = 0; i < (zend_uint)oa->last_literal; i++) {
		zend_literal *lit = &oa->literals[i];
		if (i) { fputc(',', f); }
		if (Z_TYPE(lit->constant) == IS_STRING) {
			fputc('"', f);
			json_escape(f, Z_STRVAL(lit->constant), Z_STRLEN(lit->constant));
			fputc('"', f);
		} else if (Z_TYPE(lit->constant) == IS_LONG) {
			fprintf(f, "%ld", Z_LVAL(lit->constant));
		} else if (Z_TYPE(lit->constant) == IS_DOUBLE) {
			fprintf(f, "%.17g", Z_DVAL(lit->constant));
		} else {
			const char *t = zend_get_type_by_const(Z_TYPE(lit->constant));
			fputc('"', f);
			json_escape(f, t, strlen(t));
			fputc('"', f);
		}
	}
	fputc(']', f);

	/* opcode stream */
	json_key(f, "ops");
	fputc('[', f);
	first = 1;
	for (i = 0; i < oa->last; i++) {
		zend_op *op = &oa->opcodes[i];
		const char *name = zend_get_opcode_name(op->opcode);

		if (!first) { fputc(',', f); }
		first = 0;

		jobj_open(f, '{');
		json_key(f, "i");
		fprintf(f, "%u", (unsigned)i);
		json_key(f, "op");
		if (name) {
			fputc('"', f); fputs(name, f); fputc('"', f);
		} else {
			fprintf(f, "UNKNOWN_%u", (unsigned)op->opcode);
		}
		if (op->opcode > ZEND_STANDARD_OPCODE_MAX) {
			json_key(f, "loader_opcode");
			fprintf(f, "%u", (unsigned)op->opcode);
		}
		json_key(f, "line");
		fprintf(f, "%u", op->lineno);

		if (op->result_type == IS_UNUSED) {
			json_str(f, "result", NULL);
		} else {
			json_key(f, "result");
			fprintf(f, "%u", (unsigned)op->result.var);
		}
		json_operand(f, "op1", oa, op, 1);
		json_operand(f, "op2", oa, op, 2);
		json_key(f, "op1_type");
		fprintf(f, "%u", op->op1_type);
		json_key(f, "op2_type");
		fprintf(f, "%u", op->op2_type);
		json_key(f, "result_type");
		fprintf(f, "%u", op->result_type);
		if (op->extended_value) {
			json_key(f, "ext");
			fprintf(f, "%lu", (unsigned long)op->extended_value);
		}
		jobj_close(f, '}');
	}
	fputc(']', f);
}

/* ------------------------------------------------------------------ */
/* symbol table walk                                                   */
/*                                                                     */
/* The loader registers what it decodes into EG(function_table) and     */
/* EG(class_table). Reading the op_arrays from there avoids having to   */
/* reverse the loader's declaration encoding (declarations arrive as    */
/* ZEND_NOP with the real type in extended_value).                      */
/* ------------------------------------------------------------------ */

#define ARM56_MAX_SEEN 65536
static zend_op_array *arm56_seen[ARM56_MAX_SEEN];
static int arm56_seen_count;

static int arm56_already_seen(zend_op_array *oa)
{
	int i;
	for (i = 0; i < arm56_seen_count; i++) {
		if (arm56_seen[i] == oa) { return 1; }
	}
	if (arm56_seen_count < ARM56_MAX_SEEN) {
		arm56_seen[arm56_seen_count++] = oa;
	}
	return 0;
}

static int arm56_belongs_to(zend_op_array *oa, const char *file)
{
	if (!oa || !oa->opcodes) { return 0; }
	if (!oa->filename || !file) { return 0; }
	return strcmp(oa->filename, file) == 0;
}

static void arm56_emit(FILE *f, zend_op_array *oa, const char *decl_kind, int is_main)
{
	if (arm56_already_seen(oa)) { return; }

	if (getenv("ARM56_DEBUG")) {
		fprintf(stderr, "[arm56] emit %s ops=%u lits=%d vars=%d doc=%p args=%u arginfo=%p\n",
		        oa->function_name ? oa->function_name : "(anon)",
		        (unsigned)oa->last, oa->last_literal, oa->last_var,
		        (void *)oa->doc_comment, (unsigned)oa->num_args, (void *)oa->arg_info);
	}

	dump_meta(f, oa, is_main, decl_kind, 0);
}

static long arm56_symbol_count;

/* One corrupt symbol must not cost us the whole file. The loader frees or
 * replaces literal buckets as it executes, so a fault inside one op_array is
 * expected and local: truncate back to where this symbol started and emit a
 * placeholder in its place. */
/* Installs the fault guard and returns the previous handlers so they can be
 * restored. Leaving our handler installed after the guard is torn down is
 * fatal: a later fault would siglongjmp into a jump buffer whose frame is gone. */
static void arm56_guard_install(struct sigaction *old_segv, struct sigaction *old_bus)
{
	struct sigaction sa;
	stack_t ss;

	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = arm56_fault_handler;
	sigemptyset(&sa.sa_mask);
	sa.sa_flags = SA_NODEFER | SA_ONSTACK;

	ss.ss_sp = arm56_altstack;
	ss.ss_size = sizeof(arm56_altstack);
	ss.ss_flags = 0;
	sigaltstack(&ss, NULL);

	sigaction(SIGSEGV, &sa, old_segv);
	sigaction(SIGBUS, &sa, old_bus);
}

static void arm56_guard_remove(struct sigaction *old_segv, struct sigaction *old_bus)
{
	sigaction(SIGSEGV, old_segv, NULL);
	sigaction(SIGBUS, old_bus, NULL);
}

static void arm56_emit_guarded(FILE *f, zend_op_array *oa, const char *via,
                               const char *scope)
{
	long start, mark;
	struct sigaction old_segv, old_bus;

	arm56_scope_override = scope;

	start = ftell(f);

	/* Phase 1: metadata. Every field here is readable for encoded files
	 * (name, scope, parameters, literal/opcode counts), so it is emitted
	 * unguarded and always survives. */
	arm56_guard_install(&old_segv, &old_bus);
	if (sigsetjmp(arm56_jump, 1) == 0) {
		jobj_open(f, '{');
		if (via) { json_str(f, "via", via); }
		json_str(f, "kind", kind_of(oa, 0));
		json_str(f, "name", oa->function_name);
		json_str(f, "scope", scope);
		json_str(f, "filename", oa->filename);
		json_int(f, "line_start", (long long)oa->line_start);
		json_int(f, "line_end", (long long)oa->line_end);
		json_int(f, "num_args", (long long)oa->num_args);
		json_int(f, "required_num_args", (long long)oa->required_num_args);
		json_int(f, "fn_flags", (long long)oa->fn_flags);
		json_bool(f, "is_static", (oa->fn_flags & ZEND_ACC_STATIC) != 0);
		json_bool(f, "is_abstract", (oa->fn_flags & ZEND_ACC_ABSTRACT) != 0);
		json_bool(f, "is_public", (oa->fn_flags & ZEND_ACC_PUBLIC) != 0);
		json_bool(f, "is_protected", (oa->fn_flags & ZEND_ACC_PROTECTED) != 0);
		json_bool(f, "is_private", (oa->fn_flags & ZEND_ACC_PRIVATE) != 0);
		json_int(f, "num_ops", (long long)oa->last);
		json_int(f, "num_vars", (long long)oa->last_var);
		json_int(f, "num_literals", (long long)oa->last_literal);

		if (oa->doc_comment) {
			json_key(f, "doc_comment");
			fputc('"', f);
			json_escape(f, oa->doc_comment, oa->doc_comment_len);
			fputc('"', f);
		} else {
			json_str(f, "doc_comment", NULL);
		}

		json_key(f, "args");
		fputc('[', f);
		{
			zend_uint i;
			for (i = 0; i < oa->num_args; i++) {
				if (i) { fputc(',', f); }
				jobj_open(f, '{');
				json_str(f, "name", oa->arg_info && oa->arg_info[i].name
				                 ? oa->arg_info[i].name : NULL);
				json_int(f, "type_hint", (long long)oa->arg_info[i].type_hint);
				json_str(f, "class_name", oa->arg_info && oa->arg_info[i].class_name
				                    ? oa->arg_info[i].class_name : NULL);
				json_bool(f, "pass_by_ref", oa->arg_info[i].pass_by_reference != 0);
				json_bool(f, "allow_null", oa->arg_info[i].allow_null != 0);
				json_bool(f, "is_variadic", oa->arg_info[i].is_variadic != 0);
				jobj_close(f, '}');
			}
		}
		fputc(']', f);

		/* Phase 2: the literal pool and opcode stream. For encoded files the
		 * loader keeps these encrypted until the body executes, so reading
		 * them faults. Attempt it anyway: files that did execute yield real
		 * strings, and the rest keep their metadata. */
		mark = ftell(f);
		if (sigsetjmp(arm56_jump, 1) == 0) {
			dump_content(f, oa);
			jobj_close(f, '}');
		} else {
			fflush(f);
			if (mark >= 0) {
				if (ftruncate(fileno(f), mark) != 0) { /* best effort */ }
				fseek(f, mark, SEEK_SET);
			}
			json_bool(f, "content_faulted", 1);
			jobj_close(f, '}');
			/* content was discarded; metadata stands */
		}
	} else {
		/* Phase 1 itself faulted: nothing usable for this symbol. */
		fflush(f);
		if (start >= 0) {
			if (ftruncate(fileno(f), start) != 0) { /* best effort */ }
			fseek(f, start, SEEK_SET);
		}
		fputs("{\"via\":", f);
		json_strval(f, via);
		fputs(",\"kind\":\"faulted\",\"name\":", f);
		json_strval(f, oa->function_name);
		fputs(",\"faulted\":true}", f);
	}

	arm56_guard_remove(&old_segv, &old_bus);
	arm56_scope_override = NULL;
}

static void arm56_collect_from_function_table(FILE *f, const char *file)
{
	HashTable *ht = EG(function_table);
	HashPosition pos;
	zend_function *fn;
	char *key = NULL;
	uint key_len = 0;

	if (!ht) { return; }

	if (getenv("ARM56_DEBUG")) {
		fprintf(stderr, "[arm56] walking fntable n=%d\n",
		        (int)zend_hash_num_elements(ht));
	}

	(void)pos;
	zend_hash_internal_pointer_reset(ht);
	while (zend_hash_get_current_data(ht, (void **)&fn) == SUCCESS) {
		if (getenv("ARM56_DEBUG") && fn && fn->type == ZEND_USER_FUNCTION) {
			fprintf(stderr, "[arm56] fn candidate: %s file=%s\n",
			        fn->common.function_name ? fn->common.function_name : "(anon)",
			        fn->op_array.filename ? fn->op_array.filename : "(null)");
		}
		if (!fn || fn->type != ZEND_USER_FUNCTION
		    || !arm56_belongs_to(&fn->op_array, file)) {
			zend_hash_move_forward(ht);
			continue;
		}

		if (arm56_symbol_count) { fputc(',', f); }
		arm56_emit_guarded(f, &fn->op_array, "function_table", NULL);
		arm56_symbol_count++;
		if (zend_hash_move_forward(ht) != SUCCESS) { break; }
	}
}

/* zend_hash_apply() takes no user argument, so the walk context lives here. */
static FILE *arm56_cur_f;
static const char *arm56_cur_file;


/* Methods live only in zend_class_entry->function_table in PHP 5, never in
 * EG(function_table), so classes must be resolved explicitly. The lookup
 * goes through the engine (zend_lookup_class) rather than a raw walk of
 * EG(class_table). Class names are supplied by the caller, which gets them
 * from get_declared_classes() without assuming anything about that table. */
static void arm56_collect_class_named(FILE *f, const char *class_name,
                                      const char *file)
{
	zend_class_entry **ce_ptr = NULL;
	zend_class_entry *ce;
	zend_function *mfn;

	if (getenv("ARM56_DEBUG")) {
		fprintf(stderr, "[arm56] lookup(%s) ...\n", class_name);
	}
	if (zend_lookup_class(class_name, (int)strlen(class_name), &ce_ptr TSRMLS_CC) != SUCCESS
	    || !ce_ptr || !*ce_ptr) {
		if (getenv("ARM56_DEBUG")) {
			fprintf(stderr, "[arm56]   class %s NOT FOUND\n", class_name);
		}
		return;
	}

	ce = *ce_ptr;

	if (getenv("ARM56_DEBUG")) { fprintf(stderr, "[arm56] lookup returned %p\n", (void *)ce); }

	if (getenv("ARM56_DEBUG")) {
		fprintf(stderr, "[arm56]   class %s type=%d fnts=%d\n",
		        ce->name ? ce->name : "?", (int)ce->type,
		        (int)zend_hash_num_elements(&ce->function_table));
	}

	if (ce->type != ZEND_USER_CLASS) { return; }

	zend_hash_internal_pointer_reset(&ce->function_table);
	while (zend_hash_get_current_data(&ce->function_table, (void **)&mfn) == SUCCESS) {
		if (mfn && mfn->type == ZEND_USER_FUNCTION
		    && arm56_belongs_to(&mfn->op_array, file)) {
			if (arm56_symbol_count) { fputc(',', f); }
			arm56_emit_guarded(f, &mfn->op_array, "class_table",
			                   ce->name ? ce->name : class_name);
			arm56_symbol_count++;
		}
		zend_hash_move_forward(&ce->function_table);
	}
}

/* The class list arrives as a comma-separated string rather than a PHP array:
 * the "a" specifier handed over a HashTable whose element count did not match
 * what userland reported, and walking it corrupted the heap. */
static void arm56_collect_from_class_list(FILE *f, const char *list, int len,
                                          const char *file)
{
	char *buf, *p, *end;

	if (!list || len <= 0) { return; }

	buf = emalloc(len + 1);
	memcpy(buf, list, len);
	buf[len] = '\0';

	p = buf;
	end = buf + len;

	while (p < end) {
		char *comma = memchr(p, ',', (size_t)(end - p));
		int n = comma ? (int)(comma - p) : (int)(end - p);

		if (n > 0) {
			char saved = p[n];
			p[n] = '\0';
			arm56_collect_class_named(f, p, file);
			p[n] = saved;
		}

		if (!comma) { break; }
		p = comma + 1;
	}

	efree(buf);
}

/* ------------------------------------------------------------------ */
/* output path                                                         */
/* ------------------------------------------------------------------ */

static void sanitize_into(char *dst, size_t dstsz, const char *src)
{
	size_t i, o = 0;
	size_t len = strlen(src);
	for (i = 0; i < len && o + 1 < dstsz; i++) {
		char c = src[i];
		if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
		    || (c >= '0' && c <= '9') || c == '.' || c == '-' || c == '_') {
			dst[o++] = c;
		} else {
			dst[o++] = '_';
		}
	}
	dst[o] = '\0';
}

static void dump_file(zend_file_handle *file_handle, zend_op_array *main_oa)
{
	char path[4096];
	char base[512];
	FILE *f;

	const char *outdir = arm56_outdir();

	if (!outdir || !file_handle || !file_handle->filename) { return; }

	sanitize_into(base, sizeof(base), file_handle->filename);
	snprintf(path, sizeof(path), "%s/%s.json", outdir, base);

	f = fopen(path, "wb");
	if (!f) { return; }

	arm56_seen_count = 0;

	if (getenv("ARM56_DEBUG")) {
		fprintf(stderr,
		        "[arm56] file=%s main=%p fntable=%d clstable=%d\n",
		        file_handle->filename,
		        (void *)main_oa,
		        (int)zend_hash_num_elements(EG(function_table)),
		        (int)zend_hash_num_elements(EG(class_table)));
	}

	if (sigsetjmp(arm56_jump, 1) == 0) {
		struct sigaction sa, old_segv, old_bus;
		memset(&sa, 0, sizeof(sa));
		sa.sa_handler = arm56_fault_handler;
		sigemptyset(&sa.sa_mask);
		sa.sa_flags = SA_NODEFER | SA_ONSTACK;
		{
			stack_t ss;
			ss.ss_sp = arm56_altstack;
			ss.ss_size = sizeof(arm56_altstack);
			ss.ss_flags = 0;
			sigaltstack(&ss, NULL);
		}
		sigaction(SIGSEGV, &sa, &old_segv);
		sigaction(SIGBUS, &sa, &old_bus);

		jobj_open(f, '{');
		json_str(f, "source", file_handle->filename);
		json_str(f, "stage", "compile");

		if (main_oa && main_oa->opcodes) {
			json_key(f, "main");
			dump_meta(f, main_oa, 1, NULL, 0);
			dump_content(f, main_oa);
			jobj_close(f, '}');
		}
		jobj_close(f, '}');

		sigaction(SIGSEGV, &old_segv, NULL);
		sigaction(SIGBUS, &old_bus, NULL);
	} else {
		fflush(f);
		if (ftruncate(fileno(f), 0) != 0) { /* best effort */ }
		rewind(f);
		fputs("{\"source\":", f);
		json_strval(f, file_handle->filename);
		fputs(",\"stage\":\"compile\",\"__faulted__\":true}\n", f);
	}

	fclose(f);
}

/* ------------------------------------------------------------------ */
/* compile_file hook                                                   */
/* ------------------------------------------------------------------ */

static zend_op_array *arm56_compile_file(zend_file_handle *file_handle, int type TSRMLS_DC)
{
	zend_op_array *oa = arm56_orig_compile_file(file_handle, type TSRMLS_CC);

	dump_file(file_handle, oa);

	return oa;
}

PHP_MINIT_FUNCTION(arm56)
{
	/* The loader must be the first zend_extension, so its own startup has
	 * already replaced zend_compile_file by the time this MINIT runs.
	 * Wrapping that pointer (rather than replacing it) is what lets the
	 * encoded file compile through the loader and still reach us. */
	arm56_orig_compile_file = zend_compile_file;
	zend_compile_file = arm56_compile_file;

	return SUCCESS;
}

PHP_MSHUTDOWN_FUNCTION(arm56)
{
	return SUCCESS;
}

PHP_MINFO_FUNCTION(arm56)
{
	php_info_print_table_start();
	php_info_print_table_row(2, "arm56 support", "enabled");
	php_info_print_table_row(2, "arm56 version", ARM56_VERSION);
	php_info_print_table_row(2, "arm56 json dir",
	                          arm56_outdir() ? arm56_outdir() : "(disabled)");
	php_info_print_table_end();
}

PHP_FUNCTION(arm56_version)
{
	RETURN_STRING(ARM56_VERSION, 1);
}

/* arm56_dump(string $file) -> string  (path written, or "" on failure)
 *
 * Must be called after $file has been included: PHP 5.6 binds user
 * functions into EG(function_table) during execution, not during
 * compilation, so a compile-time hook sees an empty table. */
PHP_FUNCTION(arm56_dump)
{
	char *file = NULL;
	int file_len = 0;
	char *class_list = NULL;
	int class_list_len = 0;
	char path[4096];
	char base[512];
	FILE *f;
	arm56_symbol_count = 0;

	if (getenv("ARM56_DEBUG")) {
		fprintf(stderr, "[arm56] arm56_dump called, nargs=%d\n", (int)ZEND_NUM_ARGS());
	}

	if (zend_parse_parameters(ZEND_NUM_ARGS() TSRMLS_CC, "s|s",
	                          &file, &file_len,
	                          &class_list, &class_list_len) == FAILURE) {
		if (getenv("ARM56_DEBUG")) { fprintf(stderr, "[arm56] parse FAILED\n"); }
		RETURN_FALSE;
	}

	if (getenv("ARM56_DEBUG")) {
		fprintf(stderr, "[arm56] file=%s classlist=%s outdir=%s\n",
		        file, class_list ? class_list : "(null)",
		        arm56_outdir() ? arm56_outdir() : "(null)");
	}

	{
		const char *outdir = arm56_outdir();
		if (!outdir) {
			RETURN_STRING("", 1);
		}
		sanitize_into(base, sizeof(base), file);
		snprintf(path, sizeof(path), "%s/%s.json", outdir, base);
	}

	f = fopen(path, "wb");
	if (!f) { RETURN_FALSE; }

	arm56_seen_count = 0;

	if (sigsetjmp(arm56_jump, 1) == 0) {
		struct sigaction sa, old_segv, old_bus;
		memset(&sa, 0, sizeof(sa));
		sa.sa_handler = arm56_fault_handler;
		sigemptyset(&sa.sa_mask);
		sa.sa_flags = SA_NODEFER | SA_ONSTACK;
		{
			stack_t ss;
			ss.ss_sp = arm56_altstack;
			ss.ss_size = sizeof(arm56_altstack);
			ss.ss_flags = 0;
			sigaltstack(&ss, NULL);
		}
		sigaction(SIGSEGV, &sa, &old_segv);
		sigaction(SIGBUS, &sa, &old_bus);

		jobj_open(f, '{');
		json_str(f, "source", file);
		json_str(f, "stage", "symbols");

		/* The declared class names are recorded explicitly. A marker class
		 * with no methods would otherwise leave no trace at all, and the
		 * name is the one thing reconstruction cannot invent. */
		json_key(f, "classes");
		fputc('[', f);
		if (class_list && class_list_len > 0) {
			const char *p = class_list;
			const char *end = class_list + class_list_len;
			int first = 1;
			while (p < end) {
				const char *comma = memchr(p, ',', (size_t)(end - p));
				int n = comma ? (int)(comma - p) : (int)(end - p);
				if (n > 0) {
					if (!first) { fputc(',', f); }
					first = 0;
					fputc('"', f);
					json_escape(f, p, (size_t)n);
					fputc('"', f);
				}
				if (!comma) { break; }
				p = comma + 1;
			}
		}
		fputc(']', f);

		json_key(f, "symbols");
		fputc('[', f);
		arm56_collect_from_function_table(f, file);

		arm56_collect_from_class_list(f, class_list, class_list_len, file);

		fputc(']', f);
		jobj_close(f, '}');

		sigaction(SIGSEGV, &old_segv, NULL);
		sigaction(SIGBUS, &old_bus, NULL);
	} else {
		/* A partial document is useless to the parser, so replace the whole
		 * file with a minimal valid one that records the fault. */
		fflush(f);
		if (ftruncate(fileno(f), 0) != 0) { /* best effort */ }
		rewind(f);
		fputs("{\"source\":", f);
		json_strval(f, file);
		fputs(",\"stage\":\"symbols\",\"symbols\":[],\"__faulted__\":true}\n", f);
	}

	fclose(f);

	RETURN_STRING(path, 1);
}

zend_function_entry arm56_functions[] = {
	PHP_FE(arm56_version, NULL)
	PHP_FE(arm56_dump, NULL)
	PHP_FE_END
};

zend_module_entry arm56_module_entry = {
	STANDARD_MODULE_HEADER,
	"arm56",
	arm56_functions,
	PHP_MINIT(arm56),
	PHP_MSHUTDOWN(arm56),
	NULL,
	NULL,
	PHP_MINFO(arm56),
	ARM56_VERSION,
	0,     /* globals size */
	NULL,  /* globals ptr */
	NULL,  /* globals ctor */
	NULL,  /* globals dtor */
	NULL,  /* post deactivate */
	STANDARD_MODULE_PROPERTIES_EX
};

#ifdef COMPILE_DL_ARM56
ZEND_GET_MODULE(arm56)
#endif
