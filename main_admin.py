import os
import flet as ft

os.environ["SIOR_APP_PROFILE"] = "ADMIN"

from app import main

if __name__ == "__main__":
    ft.app(target=main)