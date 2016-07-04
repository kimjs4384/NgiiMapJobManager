call "\Program Files\QGIS Essen\bin\o4w_env.bat"
call pyuic4 .\ui\extjob.ui -o .\ui\extjob_dialog_base.py
call pyuic4 .\ui\receive.ui -o .\ui\receive_dialog_base.py
call pyuic4 .\ui\inspect.ui -o .\ui\inspect_dialog_base.py