"""EVE Online Market History application entry point"""
import flet as ft
from src.app import EVEMarketApp


def main(page: ft.Page):
    """Main entry point for the application"""
    EVEMarketApp(page)


if __name__ == "__main__":
    ft.run(main)
