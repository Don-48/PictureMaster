import sys

from app.application import ImageApp


def main() -> None:
    app = ImageApp(sys.argv)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
