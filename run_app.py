import threading
import time
import webbrowser

from database.bootstrap import ensure_database_exists


def _open_browser():
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000/agenda-page", new=1)


def main():
    # 1) Create a clean DB if missing (first start)
    ensure_database_exists()

    # 2) Import Flask app AFTER DB exists
    from app import app, run_startup_migrations  # noqa: E402

    # 3) Run migrations (idempotent)
    run_startup_migrations()

    # 4) Open browser + run local server
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
