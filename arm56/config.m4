dnl config.m4 for the arm56 extension
PHP_ARG_ENABLE([arm56],
  [whether to enable arm56 support],
  [AS_HELP_STRING([--enable-arm56], [Enable arm56 op_array serialization])],
  [no])

if test "$PHP_ARM56" != "no"; then
  PHP_NEW_EXTENSION([arm56], [arm56.c], [$ext_shared], , [-Wno-unused-parameter])
fi
