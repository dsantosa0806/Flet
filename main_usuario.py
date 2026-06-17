import os
import flet as ft
from app import main

os.environ["SIOR_APP_PROFILE"] = "USUARIO"

ft.app(target=main)