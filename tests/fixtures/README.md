`sw-before-offline-map.js` is the unmodified production root worker from main
5b71275bd1af69d80ec5aa7d311faaba8e7fdea8 (cache v94). The upgrade tests serve
these actual bytes first, then the current production worker. HTML fixtures
are not synthesized, and all application resources come from the checkout.
The test isolates the worker/cache transition; it does not reconstruct every
historical page or claim complete coverage of all installed PWA versions.
All stored missions/package sentinels belong to temporary test contexts.
