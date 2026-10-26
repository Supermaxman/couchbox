"""couchbox-updater [run | check | install [VERSION] | rollback | status]   (root)"""

import json
import logging
import sys
import urllib.error

from couchbox import updater


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="couchbox-updater: %(message)s")
    args = sys.argv[1:] if argv is None else argv
    cmd = args[0] if args else "run"
    try:
        if cmd == "run":
            st = updater.run()
            print(json.dumps({k: st.get(k) for k in ("available", "waiting", "last_error")}))
        elif cmd == "check":
            m = updater.check()
            print(f"Update available: {m['version']}" if m else f"Up to date ({updater.__version__}).")
        elif cmd == "install":
            if len(args) > 1:
                st = updater.load_state()
                st["available"] = args[1]
                updater.save_state(st)
            st = updater.run(force_install=True)
            print(f"Installed {st.get('just_updated', {}).get('version', '?')}." if st.get("just_updated") else "Nothing to install.")
        elif cmd == "rollback":
            updater.rollback()
            print("Rolled back.")
        elif cmd == "status":
            print(json.dumps(updater.status(), indent=2))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except updater.UpdateError as e:
        print(f"couchbox-updater: {e}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as e:
        print(f"couchbox-updater: can't reach the update server ({getattr(e, 'reason', e)})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
