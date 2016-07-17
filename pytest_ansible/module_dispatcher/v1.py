import logging
import warnings

# conditionally import ansible libraries
import ansible
import ansible.constants
import ansible.utils
import ansible.errors

from pkg_resources import parse_version
has_ansible_v1 = parse_version(ansible.__version__) < parse_version('2.0.0')

if not has_ansible_v1:
    raise ImportError("Only supported with ansible < 2.0")

from ansible.runner import Runner
from pytest_ansible.module_dispatcher import BaseModuleDispatcher
from pytest_ansible.errors import AnsibleConnectionFailure
from pytest_ansible.results import AdHocResult

try:
    from logging import NullHandler
except ImportError:
    from logging import Handler

    class NullHandler(Handler):

        def emit(self, record):
            pass

log = logging.getLogger(__name__)
log.addHandler(NullHandler())


class ModuleDispatcherV1(BaseModuleDispatcher):

    '''Pass.'''

    required_kwargs = ('inventory', 'inventory_manager', 'host_pattern')

    def has_module(self, name):
        return ansible.utils.module_finder.has_plugin(name)

    def _run(self, *module_args, **complex_args):
        '''
        The API provided by ansible is not intended as a public API.
        '''

        # Assemble module argument string
        if True:
            module_args = ' '.join(module_args)
        else:
            if module_args:
                complex_args.update(dict(_raw_params=' '.join(module_args)))

        # Assert hosts matching the provided pattern exist
        hosts = self.options['inventory_manager'].list_hosts()
        no_hosts = False
        if len(hosts) == 0:
            no_hosts = True
            warnings.warn("provided hosts list is empty, only localhost is available")

        self.options['inventory_manager'].subset(self.options.get('subset'))
        hosts = self.options['inventory_manager'].list_hosts(self.options['host_pattern'])
        if len(hosts) == 0 and not no_hosts:
            raise ansible.errors.AnsibleError("Specified hosts and/or --limit does not match any hosts")

        # Log the module and parameters
        log.debug("[%s] %s: %s" % (self.options['host_pattern'], self.options['module_name'], complex_args))

        # Build module runner object
        kwargs = dict(
            inventory=self.options.get('inventory_manager'),
            pattern=self.options.get('host_pattern'),
            module_name=self.options.get('module_name'),
            module_args=module_args,
            complex_args=complex_args,
            transport=self.options.get('connection'),
            remote_user=self.options.get('user'),
            module_path=self.options.get('module_path'),
            become=self.options.get('become'),
            become_method=self.options.get('become_method'),
            become_user=self.options.get('become_user'),
        )

        # Run the module
        runner = Runner(**kwargs)
        results = runner.run()

        # Log the results
        log.debug(results)

        if 'dark' in results and results['dark']:
            raise AnsibleConnectionFailure("Host unreachable", dark=results['dark'], contacted=results['contacted'])

        # Success!
        return AdHocResult(contacted=results['contacted'])
