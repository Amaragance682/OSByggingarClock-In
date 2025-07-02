1.

install python:

python --version


2.

move this project to a directory on the computer


3.

move to project folder and activate a python virtual environment:

cd ../projectFolder

python -m venv venv


4. 

activate it:

windows => venv/Scripts/activate
linux/mac => source venv/bin/activate


5.

run these 2 commands in the root folder of the project, (where setup.py is located)

pip install --upgrade pip
pip install .


6.

verify installation of scripts:

cmd /c "app.bat"     <-- employee application
cmd /c "view.bat"    <-- admin view
cmd /c "export.bat"  <-- export data to excel reports located in /Database/reports/





EXTRA:
rebuild .spec files for .EXE files:

pyinstaller export_company_reports.spec
pyinstaller app.spec
pyinstaller admin_view.spec