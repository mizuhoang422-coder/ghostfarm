"""Chay scan history trong subprocess rieng, khong conflict event loop."""
import sys, time
sys.path.insert(0, ".")
import storage
storage.init()
from bot import scan_history_once
scan_history_once()
