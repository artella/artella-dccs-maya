import os
import sys
import json
import platform
import logging
import subprocess

logging.basicConfig(level=logging.INFO)


def parse(file_paths, projects_path=None, recursive=True):
    mayapy_path = get_mayapy_path()
    logging.info('Using MayaPy: {}'.format(mayapy_path))
    parser_script = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'scripts', 'maya_parser.py')

    out, err = run_python_script_in_maya(
        mayapy_path, parser_script, maya_files=file_paths, projects_path=projects_path, recursive=recursive)

    out_str = str(out or '')
    err_str = str(err or '')
    output_dict = dict()
    if out_str:
        out_split = out_str.split('\n')
        for out_line in out_split:
            if out_line.startswith('ARTELLA PARSER OUTPUT:'):
                output_dict_str = out_line[len('ARTELLA PARSER OUTPUT:'):]
                if output_dict_str:
                    output_dict.update(json.loads(output_dict_str))
                    break
    output_dict['log'] = out_str
    output_dict['error'] = err_str

    return output_dict


def get_maya_install_folder(version):

    maya_location = None
    if platform.system().lower() =='windows':
        try:
            import winreg
        except ImportError:
            import _winreg as winreg
        a_reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)

        value = None
        try:
            a_key = winreg.OpenKey(a_reg, r"SOFTWARE\Autodesk\Maya\{}\Setup\InstallPath".format(version))
            value = winreg.QueryValueEx(a_key, 'MAYA_INSTALL_LOCATION')
        except Exception:
            return None
        finally:
            if not value:
                return None
        maya_location = value[0]
        if not maya_location:
            return None
    elif platform.system().lower() == 'darwin':
        maya_paths = ['/Applications/Maya {}/Maya.app', 'Library/Preferences/Autodesk/Maya/{}']
        for maya_path in maya_paths:
            maya_path = maya_path.format(version)
            if not os.path.isdir(maya_path):
                continue
            maya_location = maya_path
            break

    return maya_location


def get_mayapy_path(version=None):

    python_executable = sys.executable
    if platform.system().lower() == 'windows':
        if os.path.basename(python_executable) == 'mayapy.exe':
            return python_executable
        elif os.path.basename(python_executable) == 'maya.exe':
            maya_py_path = os.path.join(os.path.dirname(python_executable), 'mayapy.exe')
            if os.path.isfile(maya_py_path):
                return maya_py_path
    elif platform.system().lower() == 'darwin':
        if os.path.basename(python_executable) == 'mayapy':
            return python_executable
        elif os.path.basename(python_executable) == 'Maya':
            maya_py_path = os.path.join(os.path.dirname(os.path.dirname(python_executable)), 'bin', 'mayapy')
            if os.path.isfile(maya_py_path):
                return maya_py_path

    maya_versions = [version] if version is not None else [2020, 2019, 2018, 2017]  # start with the newest one
    for maya_version in maya_versions:
        maya_install_path = get_maya_install_folder(maya_version)
        if not maya_install_path or not os.path.isdir(maya_install_path):
            continue

        maya_py_path = None
        if platform.system().lower() == 'windows':
            maya_py_path = os.path.join(maya_install_path, 'bin', 'mayapy.exe')
        elif platform.system().lower() == 'darwin':
            maya_py_path = os.path.join(maya_install_path, 'bin', 'mayapy')
        if not maya_py_path or not os.path.isfile(maya_py_path):
            continue

        return maya_py_path


def run_python_script_in_maya(mayapy_path, python_script_file, environ=None, *args, **kwargs):
    if not mayapy_path or not os.path.isfile(mayapy_path):
        return '', "{} is not a valid Maya Python interpreter path".format(mayapy_path)

    interpreter = mayapy_path

    runtime_env = os.environ.copy()
    if environ:
        runtime_env = environ.copy()
    # set both of these to make sure maya auto-configures it's own libs correctly
    runtime_env['MAYA_LOCATION'] = os.path.dirname(interpreter)
    runtime_env['PYTHONHOME'] = os.path.dirname(interpreter)
    runtime_env['PYTHONPATH'] = ''
    runtime_env['PATH'] = ''

    arg_string = ""
    if len(args):
        arg_string = " ".join(map(str, *args))

    kwargs_string = ''
    for k, v in kwargs.items():
        if isinstance(v, (list, tuple)):
            kwargs_string += '--{} '.format(k)
            for item in v:
                kwargs_string += '"{}" '.format(item)
        else:
            kwargs_string += '--{}="{}" '.format(k, v)

    cmd_string = '''"%s" "%s" %s %s''' % (interpreter, python_script_file, arg_string, kwargs_string)

    clean_env = dict()
    for k, v in runtime_env.items():
        clean_env[k] = str(v)

    runner = subprocess.Popen(
        cmd_string, env=clean_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
    return runner.communicate()


if __name__ == '__main__':
    # file_paths = [r"D:\shorts\artella-files\06 Flight Assets\06 Flight Assets\Arc Dragon\arcTheDragon_v1.61.ma"]
    # file_paths = [r"D:\shorts\artella-files\Showcase 2020\Production\Shot_114\Assets\overlord_baker.ma"]
    projects_path = r'D:\shorts\artella-files'
    file_paths = [r"D:\shorts\artella-files\Crucible\Production\Seq-001\Shot-001\Anim\Shot-001-anim.ma"]
    parse(file_paths, projects_path=projects_path)
