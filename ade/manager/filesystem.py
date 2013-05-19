'''
FileSystemManager manager

Construct and parse results of the teplate manager

'''
import os
import re
import logging

from template import TemplateManager

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('FileSystemManager')

# DEFAULT REGEX FOR COMMON FOLDER TYPES
regexp_config = {
    'show': '(?P<show>[a-zA-Z0-9_]+)',
    'sequence': '(?P<sequence>[a-zA-Z0-9_]+)',
    'shot': '(?P<shot>[a-zA-Z0-9_]+)',
    'department': '(?P<department>[a-z_]+)'
}


class FileSystemManager(object):

    def __init__(self, template_manager=None):
        self.__default_path_regex = '(?P<{0}>[a-zA-Z0-9_]+)'
        if (template_manager and not isinstance(template_manager, TemplateManager)):
            log.exception('{} is not a valid template Namager')

        self.template_manager = template_manager or TemplateManager()

    def build(self, name, data, root=None):
        ''' Build the given schema name, and replace data,
        level defines the depth of the built paths.

        :param name: The template *name* to build.
        :type name: str
        :param data: A set of data to create the template with.
        :type name: dict
        :param root: Define the start path of the tree to be build.
        :type name: str
        
        '''
        current_path = root
        built = self.template_manager.resolve_template(name)
        results = self.template_manager.resolve(built)
        path_results = self._to_path(results, data)
        for result in path_results:
            path = os.path.join(current_path, result['path'])
            if result['folder']:
                # Create the folder
                log.debug('creating folder: {0}'.format(path))
                try:
                    os.makedirs(path)
                except Exception, error:
                    log.debug(error)
                    pass
            else:
                log.debug('creating file: {0}'.format(path))
                file_content = result['content']
                try:
                    f = open(path, 'w')
                    f.write(file_content)
                    f.close()
                except IOError, error:
                    log.debug(error)
                    pass

        # Set permissions, using the reversed results
        for result in reversed(path_results):
            path = os.path.join(current_path, result['path'])
            permission = result['permission']
            log.debug('setting {0} for {1}'.format(
                oct(permission), os.path.realpath(path))
            )
            try:
                os.chmod(path, permission)
            except OSError, error:
                log.debug(error)

    def parse(self, path, name):
        ''' Parse the provided path against
        the given schema name.

        :param path: The *path* to be parsed.
        :type path: str
        :param name: The teplate name to parse against.
        :type name: str

        '''
        matched_results = []
        built = self.template_manager.resolve_template(name)
        results = self.template_manager.resolve(built)
        parsers = self._to_parser(results)

        for parser in parsers:
            check = re.compile(parser)
            match = check.match(path)

            if not match:
                continue

            result = match.groupdict()
            if result and result not in matched_results:
                matched_results.append(result)

        matched_results.sort()
        matched_results.reverse()
        return matched_results

    def _to_parser(self, paths):
        ''' Recursively build a parser from the
        given set of schema paths

        '''
        result_paths = []
        for path in paths:
            result_path = []
            path = path['path']
            for entry in path:
                if '+' in entry:
                    entry = entry.split('+')[1]
                    # Get the custom regex or use the default one
                    parser = regexp_config.get(
                        entry,
                        self.__default_path_regex
                    )
                    entry = parser.format(entry)
                result_path.append(entry)
            result_path = (os.sep).join(result_path)
            result_paths.append(result_path)
        return result_paths

    def _to_path(self, paths, data):
        ''' Recursively build a list of paths from the given
        set of schema paths.

        '''
        result_paths = []
        for entry in paths:
            result_path = []
            for item in entry['path']:
                if '+' in item:
                    item = item.split('+')[1]
                    item = '{%s}' % item
                result_path.append(item)

            if result_path not in result_paths:
                final_path = (os.sep).join(result_path)
                try:
                    final_path = final_path.format(**data)
                except Exception, error:
                    log.warning(
                        'PATHSKIP: {1} not found for {0}'.format(
                            final_path,
                            error
                        )
                    )
                    continue

                entry['path'] = final_path
                result_paths.append(entry)

        return result_paths
