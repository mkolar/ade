'''
Structure manager

Provide a convenient class to construct virtual file path mapping
from a folder containing fragments.

'''
import os
import re
import stat
import copy
from operator import itemgetter

try:
    import efesto_logger as logging
except:
    import logging

logger = logging.getLogger(__name__)


class TemplateManager(object):
    ''' Template manager class,
    Provide standard methods to create virtual file structure
    from disk fragments.

    :param template_folder: The path to the config folder.
    :type template_folder: str

    '''
    def __init__(self, config=None):
        ''' Initialization function.

        '''
        # current_path = os.path.dirname(os.path.abspath(__file__))
        self.__reference_indicator = '@'
        self.__variable_indicator = '+'

        self._register = []
        template_folder = config.get('template_search_path')
        self._template_folder = os.path.realpath(template_folder)
        logger.debug(
            'Using template path: {0}'.format(self._template_folder)
        )
        self.register_templates()

        def sanitize(var):
            if not var:
                return None

            if '@' in var:
                var = var.replace('@', '')

            if '+' in var:
                var = var.replace('+', '')

            return var

        def sort_children(reg_item):
            if len(reg_item.get('children', [])):
                sorted_children = sorted(
                    reg_item.get('children', []),
                    key= lambda x : (not(x.get('folder')), sanitize(x.get('name')).lower()))

                reg_item['children'] = sorted_children
                for child in reg_item['children']:
                    sort_children(child)

        for reg_item in self._register:
            sort_children(reg_item)

        self._register = sorted(self._register, key= lambda x : (sanitize(x.get('name')).lower()))

    @property
    def register(self):
        ''' Return the templates registered.
        '''
        return self._register

    def find_path(self, startwith=None, contains=None, endswith=None, template_name='@+show+@'):
        ''' Finds a path based on some filtering arguments.

        :param startwith: filters out paths that do not start with this element
        :type startwith: string
        :param contains: filters out paths that do not contain what in this list
        :type contains: list
        :param endswith: filters out paths that do not end with this element
        :type endswith: string
        :param template_name: where to start resolving the template from
        :type template_name: string
        :return: the first matched path
        :rtype: ``list``
        '''

        def sanitize(var):
            if not var:
                return None

            if '+' in var:
                var = var.replace('+', '')

            if '{' in var:
                var = var[1:-1]

            return var

        built = self.resolve_template(template_name)
        resolved = self.resolve(built)
        paths = [item['path'] for item in resolved]
        # paths = sorted(paths, key= lambda x : [len(y) for y in x])

        startwith = sanitize(startwith) or None
        endswith = sanitize(endswith) or None
        contains = map(sanitize, contains or []) or []

        logger.debug(
            '\n---------------------------\n'
            'Filters are:\n'
            'Starts with: %s\n'
            'Contains: %s\n'
            'Ends with: %s\n'
            '-----------------------------'
            % (startwith, contains, endswith)
        )

        for path in paths:
            logger.debug('Filtering against path %s' % path)

            sanitized_last_path_item = sanitize(path[-1])
            sanitized_first_path_item = sanitize(path[0])

            _start = startwith == sanitized_first_path_item if startwith else True
            _ends = endswith == sanitized_last_path_item if endswith else True

            outs = []
            for item_in_contains in contains:
                is_in = False

                for path_element in path:
                    if item_in_contains in path_element:
                        is_in = True
                        outs.append(is_in)
                if is_in == False:
                    outs.append(is_in)


            _contains = all(outs)

            if all([_start, _ends, _contains]):
                return path
        else:
            logger.debug(
                'Could not find a path that matches the criteria:\n'
                'Starts with: %s\n'
                'Contains: %s\n'
                'Ends with: %s'
                % (startwith, contains, endswith)
            )

    def resolve(self, schema):
        ''' Resolve the given *schema* data and return all the entries.

            :param schema: The schema to resolve.
            :type schema: dict
            :returns:  list -- the resolved paths.
            :raises: AttributeError, KeyError

            .. code-block:: python

                from ade.schema.template import TemplateManager

                manager = TemplateManager('./templates')
                schema = manager.resolve_template('@+show+@')
                resolved_schema = manager.resolve_template(schema)

        '''
        root_name = schema.get('name').replace(self.__reference_indicator, '')
        root = dict(
            path=[root_name],
            permission=schema.get('permission', 777),
            folder=schema.get('folder', True),
            content=schema.get('content', '')
        )

        paths = [root_name]

        result_paths = []
        self._resolve(
            schema,
            result_paths,
            paths
        )

        #paths = sorted(paths, key= lambda x : [len(y) for y in x])
        #result_paths.reverse()
        result_paths.insert(0,root)

        #paths.sort(key=lambda x: len(x['path']))
        return result_paths

    def _resolve(self, schema, final_path_list, path=None):
        ''' Recursively build the final_path_list from schema.

        :param schema: The *schema* informations
        :type name: str
        :param final_path_list: The resolved list of paths
        :type name: list
        :param path: An internal memory reference for the recursive function.
        :type name: list

        .. note::
            This function is meant to be called only from within
            the resolve function

        '''
        for index, entry in enumerate(schema.get('children', [])):
            name = entry.get('name')
            name = name.replace(self.__reference_indicator, '')
            path.append(name)
            current_path = path[:]

            new_entry = dict(
                path=current_path,
                permission=entry.get('permission', 777),
                folder=entry.get('folder', True),
                content=entry.get('content', '')
            )

            final_path_list.append(
                new_entry
            )
            self._resolve(entry, final_path_list, path)

            path.pop()

    def _get_in_register(self, name):
        ''' Return a copy of the given schema name in register.

            :param name: The template *name*.
            :type name: str
            :returns:  dict -- the found template.
            :raises: KeyError

            .. code-block:: python

                from ade.schema.template import TemplateManager
                from ade.schema.config import ConfigManager

                config_manager = ConfigManager('path/to/config')
                manager = TemplateManager(config_manager)
                schema = manager._get_in_register('@+show+@')

        '''
        msg = 'template %s not found in register'

        for item in self.register:
            if not item.get('name') == name:
                # logger.debug((msg % name) + '... keep looking')
                continue

            #logger.debug('found template %s ' % name)
            item = copy.deepcopy(item)
            return item

        logger.error(msg % name)
        raise KeyError(msg % name)

    def resolve_template(self, name):
        ''' Return the built schema fragment of the given variable *name*.

            :param name: The template *name*.
            :type name: str
            :returns:  dict -- the resolved template.
            :raises: AttributeError, KeyError

            .. code-block:: python

                from ade.schema.template import TemplateManager
                from ade.schema.config import ConfigManager

                config_manager = ConfigManager('path/to/config')
                manager = TemplateManager(config_manager)
                schema = manager.resolve_template('@+show+@')

        '''
        root = self._get_in_register(name)
        self._resolve_template(
            root,
        )

        def sanitize(var):
            if not var:
                return None

            if '@' in var:
                var = var.replace('@', '')

            if '+' in var:
                var = var.replace('+', '')

            return var

        def sort_children(chunk):
            if len(chunk.get('children', [])) > 0:
                sorted_children = sorted(chunk.get('children', []), key= lambda x : (not(x.get('folder')), sanitize(x.get('name')).lower()))
                chunk['children'] = sorted_children
                for child in chunk['children']:
                    sort_children(child)

        sort_children(root)

        return root

    def _resolve_template(self, schema):
        ''' Recursively resolve in place the given *schema* schema.

        :param name: The *schema* template to be resolved.
        :type name: dict

        .. note::
            This function is meant to be called only from within
            the resolve_template function.

        '''


        for index, entry in enumerate(schema.get('children', [])):
            item = entry.get('name', '')
            #logger.debug('resolving item %s' % item)
            if self.__reference_indicator in item:
                removed = schema['children'].pop(index)
                fragment = self._get_in_register(removed['name'])
                if removed.get('children'):
                    fragment['children'].extend(removed['children'])

                schema['children'].insert(index, fragment)
                self._resolve_template(fragment)
            else:
                self._resolve_template(entry)

    def register_templates(self, template_folder=None):
        ''' Parse template path and fill up the register table.

            :param template_folder: The template path.
            :type template_folder: str

            .. code-block:: python

                from ade.schema.template import TemplateManager

                manager = TemplateManager()
                manager.register_templates('some/path/to/template')
        '''
        template_folder = template_folder or self._template_folder
        template_path = os.path.realpath(template_folder)
        templates = os.listdir(template_path)

        # For each template root, recursively walk the content,
        # and register the hierarcy path in form of dictionary
        for template in templates:
            current_template_path = os.path.join(template_path, template)
            permission = oct(stat.S_IMODE(
                os.stat(current_template_path).st_mode
            ))

            current_template_map = dict(
                name=template,
                children=[],
                permission=permission,
                folder=True
            )

            self._register_templates(
                current_template_path,
                current_template_map['children']
            )

            self._register.append(current_template_map)

    def _register_templates(self, root, mapped):
        ''' Recursively fill up the given *mapped* object with the
        hierarchical content of *root*.

        :param root: The root path.
        :type root: str

        :param mapped: The destination mapping.
        :type mapped: dict

        .. note::
            This recursive function is meant to be called only
            from within the register_template function

        '''
        # If the root is a folder
        if os.path.isdir(root):

            # Collect the content
            entries = os.listdir(root)
            entries = sorted(entries, key=lambda x : os.path.isfile(os.path.join(root, x)))

            for entry in entries:
                if entry.startswith('.git'):
                    continue

                subentry = os.path.join(root, entry)
                permission = oct(stat.S_IMODE(os.stat(subentry).st_mode))

                item = dict(
                    name=entry,
                    permission=permission,
                    folder=False
                )

                if os.path.isdir(subentry):
                    # If it's a folder, mark it with children and type
                    item['folder'] = True
                    item['children'] = []

                    # Continue searching in folder
                    self._register_templates(subentry, item['children'])
                else:
                    # If it's a file store the content
                    item['content'] = open(subentry, 'r').read()


                mapped.append(item)
