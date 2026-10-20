# PR 360 integration checks, 20 October 2026

- Main base: 19c236e189c27e561c367aa9b073d5d55777c1a5.
- Local unit: 806 passed, 7 skipped (external research/native FFmpeg).
- PostgreSQL broad suite: 282 passed; Redis test was rerun with isolated Redis.
- Focused municipal/hourly/Redis integration: 22 passed, including the formerly missing Redis check.
- Province/TOP/map browser suite: 48 passed.
- TOP priority and persistent geography: 7 passed.
- Formerly failing real HTTP full-stack desktop/mobile scenarios: 10 passed.
- TypeScript, Ruff, Mypy, i18n, production build, supply-chain and bundle checks pass.
- Manual production workflow YAML/Bash syntax and Compose override validate.
- Deployment uses paginated PR files and checks; complete file count is verified.
- Test-only geocoder harness lives outside app and is mounted only by the explicit full-stack Compose override. Production cannot import it.
- Original 0064 geography expansion is now unreleased 0065, following main's hourly migration. Immutable released migrations remain unchanged.

Production audit and Payment audit passed on GitHub for 188436c9. Full audit then exposed legacy synthetic address fixtures; Mobile validation exposed missing JSON import attributes during Node collection. Both are corrected in the next commit and require a fresh GitHub run.
