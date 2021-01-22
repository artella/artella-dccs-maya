import os
import sys
import json
import argparse
import traceback
from collections import OrderedDict

import maya.cmds as cmds


SUPPORTED_FILE_TYPES = {
    '.ma': {'type': 'mayaAscii', 'plugin': None},
    '.mb': {'type': 'mayaBinary', 'plugin': None}
}

# GLobal dictionary that contains information of the current execution of the script
out = {
    'success': False,
    'log': '',
    'msg': '',
    'result': None
}


def clean_path(path):
    """
    Returns a cleaned path to make sure that we do not have problems with path slashes
    :param str path: path we want to clean
    :return: clean path
    :rtype: str
    """

    # Convert '~' Unix char to user's home directory and remove spaces and bad slashes
    if sys.version_info.major == 2:
        if isinstance(path, str):
            path = os.path.expanduser(path)
        else:
            path = os.path.expanduser(str(path.encode('utf-8')))
    path = str(path.replace('\\', '/').replace('//', '/').rstrip('/').strip())

    # Fix server paths
    is_server_path = path.startswith('\\')
    while '\\' in path:
        path = path.replace('\\', '//')
    if is_server_path:
        path = '//{}'.format(path)

    # Fix web paths
    if not path.find('https://') > -1:
        path = path.replace('//', '/')

    return path


def new_file(force=True):
    """
    Creates a new Maya scene cleaning the contents of the current one

    :param force: bool, If True, no save window will be prompted
    """

    cmds.file(new=True, f=force)


def open_file(file_path, force=True):
    """
    Opens Maya scene file

    :param file_path: str, file path pointing to a valid Maya scene file
    :param force: bool, If True, not save window will be prompted
    """

    cmds.file(file_path, o=True, f=force)


def current_scene():
    """
    Returns file path of the current opened Maya scene file

    :return: Absolute path to Maya scene file
    :rtype: str
    """

    return cmds.file(query=True, sceneName=True)


def list_dependencies():
    """
    List all dependency file paths of the current Maya scene file

    :return: Lst of all dependency file paths in current Maya scene
    :retype: list(str)
    """

    reference_files = list_references() or list()
    texture_files = list_textures() or list()

    all_dependencies = list(set(reference_files + texture_files))

    return all_dependencies


def list_references():
    """
    List all reference file paths of the current Maya scene file

    :return: Lst of all reference file paths in current Maya scene
    :retype: list(str)
    """

    reference_nodes = cmds.ls(type='reference')

    # Check for reference nodes
    reference_files = list()
    for reference_node in reference_nodes:
        if reference_node in ['sharedReferenceNode']:
            continue
        try:
            reference_file = cmds.referenceQuery(reference_node, filename=True)
        except RuntimeError:
            continue
        reference_files.append(reference_file)

    return reference_files


def list_textures():
    """
    List all texture file paths of the current Maya scene file

    :return: Lst of all texture file paths in current Maya scene
    :retype: list(str)
    """

    file_nodes = cmds.ls(type='file')

    texture_files = list()
    for file_node in file_nodes:
        if not cmds.attributeQuery('fileTextureName', node=file_node, exists=True):
            out['log'] += 'File node "{}" has no fileTextureName attribute. Skipping ...\n'.format(file_node)
            continue
        file_path = cmds.getAttr('{}.fileTextureName'.format(file_node))
        if not file_path:
            continue
        texture_files.append(file_path)

    return texture_files


def import_file(file_path, force=True):
    file_ext = os.path.splitext(file_path)[-1]
    import_arguments = {
        'i': True, 'f': force, 'returnNewNodes': True, 'ignoreVersion': True, 'renameAll': True, 'options': 'v=0;',
        'preserveReferences': True, 'importFrameRate': True, 'importTimeRange': 'override'
    }
    file_type_data = SUPPORTED_FILE_TYPES.get(file_ext, None)
    if file_type_data:
        import_arguments['type'] = file_type_data['type']

    try:
        cmds.file(file_path, **import_arguments)
        return True
    except Exception as exc:
        out['success'] = False
        out['msg'] = 'Impossible to import file "{}" : {}'.format(file_path, exc)
        return False


def get_dependency_paths(file_path):
    new_file(force=True)

    out['log'] += 'Getting dependencies: {}\n'.format(file_path)
    dependencies_list = list()
    if not file_path or not file_path.endswith(('.ma', '.mb')):
        return dependencies_list

    if not file_path or not os.path.isfile(file_path):
        out['success'] = False
        out['msg'] = 'File path to get dependencies from does not exist: "{}"'.format(file_path)
        return dependencies_list

    new_file(force=True)
    valid_import = False
    try:
        valid_import = import_file(file_path, force=True)
    except Exception:
        pass
    if not valid_import:
        try:
            open_file(file_path, force=True)
        except Exception as exc:
            out['success'] = False
            out['msg'] = 'Something went wrong while getting dependencies: \n{}'.format(exc)
            return dependencies_list

    try:
        dependencies_list.extend(list_dependencies())
    except Exception:
        out['success'] = False
        out['msg'] = 'Something went wrong while getting dependencies in file "{}": "{}"'.format(
            file_path, traceback.format_exc())
        return dependencies_list

    out['log'] += 'Dependencies found: {}\n'.format(dependencies_list)

    return list(set(dependencies_list))


def parse(file_paths, recursive=True):

    if not file_paths:
        return list()

    errors = OrderedDict()
    dependencies_paths = dict()
    for file_path in file_paths:
        print('ARTELLA: Parsing {} ...'.format(file_path))
        if not file_path:
            continue
        try:
            file_path = clean_path(file_path)
            dependencies_paths.setdefault(file_path, list())
            file_path = os.path.normpath(os.path.expandvars(file_path))
            file_path = clean_path(file_path)
            file_dependencies = get_dependency_paths(file_path)
            dependencies_paths[file_path].extend(file_dependencies or list())
            if recursive:
                parse(file_dependencies, recursive=recursive)
        except Exception as exc:
            errors[file_path] = str(exc)

    return dependencies_paths, errors


if __name__ == '__main__':
    import maya.standalone as standalone

    parser = argparse.ArgumentParser(description='Parses Maya files recursively looking for file paths')
    parser.add_argument('--maya_files', nargs='+', help='Path of Maya files we want to parse.')
    parser.add_argument('--projects_path', required=False, help='Path where Artella project files are located')
    parser.add_argument(
        '--recursive', required=False, help='Whether dependencies should be retrieved in a recursive way', default=True)
    args = parser.parse_args()

    if not args.projects_path or not os.path.isdir(args.projects_path):
        projects_path = os.environ.get('ART_LOCAL_ROOT', None)
    else:
        projects_path = args.projects_path
    if not projects_path or not os.path.isdir(projects_path):
        out['success'] = False
        out['msg'] = 'Impossible to parse files because no Artella projects path defined!'
    else:
        os.environ['ART_LOCAL_ROOT'] = projects_path
        # Make sure that user setup files are not executed
        os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
        standalone.initialize(name='python')

        parsed_files, error = parse(args.maya_files, recursive=args.recursive)
        out['success'] = True
        out['result'] = parsed_files
        out['error'] = error

    try:
        out_str = json.dumps(out)
    except Exception as exc:
        out['success'] = False
        out['log'] = 'Parsed process was completed but was not possible to serialize output data.'
        out['msg'] = str(exc)
        out['result'] = None
        out_str = json.dumps(out)

    print('ARTELLA PARSER OUTPUT:{}'.format(out_str))
