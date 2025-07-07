from setuptools import setup, find_packages

setup(
    name="ShiftManager",
    version="1.0.0",
    author="Óli",
    description="A multi-role PC application for managing employee shifts and reports.",
    packages=find_packages(include=['lib', 'shared', 'apps', 'lib.*', 'shared.*', 'apps.*']),
    install_requires=[
        "Pillow>=10.0.0",
        "openpyxl>=3.1.2",
        "tktimepicker @ git+https://github.com/noklam/tktimepicker.git",
        "appdirs>=1.4.4",
        "tk",  # Tkinter (note: for some environments, this is included with Python)
        "pyinstaller>=6.0.0",  # For packaging as executable
        "pystray>=0.19.4",     # For system tray integration
        "pywin32>=306; platform_system=='Windows'",  # Windows-specific features
        "pyqt5>=5.15.9",       # If any Qt GUIs are used
        "requests>=2.31.0",    # For HTTP requests
        "python-dotenv>=1.0.0" # For .env config files
    ],
    entry_points={
        'console_scripts': [
            'employee-app=employee_app:main',
            'admin-app=admin_app:main',
            'report-generator=report_generator:main',
        ]
    },
    include_package_data=True,
    package_data={
        '': ['*.json', '*.png', '*.txt'],
    },
    python_requires='>=3.10',
)
