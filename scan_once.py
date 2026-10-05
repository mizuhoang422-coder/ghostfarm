def run():
    import sys, time
    sys.path.insert(0, ".")
    from bot import scan_history_once
    try:
        scan_history_once()
    except Exception as e:
        print(f"[scan_once] {e}")

if __name__ == "__main__":
    run()
