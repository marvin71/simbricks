# Copyright 2024 Max Planck Institute for Software Systems, and
# National University of Singapore
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from simbricks.orchestration.experiments import Experiment
from simbricks.orchestration import nodeconfig as nc
from simbricks.orchestration import simulators as sims
from simbricks.orchestration import e2e_topologies
import typing as tp
from simbricks.utils import generate_homa_cmds
import ipaddress

class HomaApp(nc.AppConfig):

    def __init__(self, kernel_parameters = {}) -> None:
        super().__init__()
        self.hosts_file = ''
        self.commands = []
        self.kernel_parameters = {
            '.net.homa.max_gso_size': 1500,
        }
        self.kernel_parameters.update(kernel_parameters)

    # pylint: disable=consider-using-with
    def config_files(self) -> tp.Dict[str, tp.IO]:
        m = {
            'cp_node': open('../images/homa/util/cp_node', 'rb'),
            'homa_prio': open('../images/homa/util/homa_prio', 'rb'),
            'hosts': self.strfile(self.hosts_file),
        }
        return {**m, **super().config_files()}

    def prepare_post_cp(self, node: nc.NodeConfig) -> tp.List[str]:
        return super().prepare_post_cp(node) + [
            f'sysctl {k}={v}' for k, v in self.kernel_parameters.items()
        ]

    def run_cmds(self, node: nc.NodeConfig) -> tp.List[str]:
        return self.commands


experiments = []

def add_exp(name, n_racks, h_per_rack, opts, clients, servers, net_opts={}):
    parser = generate_homa_cmds.get_parser()
    options = parser.parse_args('')

    options.num_nodes = n_racks * h_per_rack
    options.no_rtt_files = opts['no_rtt_files']
    options.seconds = opts['app_time']
    options.client_ports = opts['client_ports']
    options.port_receivers = opts['port_receivers']
    options.client_max = opts['client_max']
    options.server_ports = opts['server_ports']
    options.port_threads = opts['port_threads']
    options.workload = opts['workload']
    options.protocol = opts['protocol']
    options.tcp_client_ports = opts['tcp_client_ports']
    options.tcp_port_receivers = opts['tcp_port_receivers']
    options.tcp_server_ports = opts['tcp_server_ports']
    options.tcp_port_threads = opts['tcp_port_threads']
    options.unloaded = opts['unloaded']
    options.no_homa_prio = opts['no_homa_prio']

    generate_homa_cmds.init(options)
    generate_homa_cmds.start_servers(servers, options)
    generate_homa_cmds.run_experiment(name, clients, options)
    generate_homa_cmds.stop_nodes()

    ipn = ipaddress.ip_network('10.3.0.0/16')
    ips = ipn.hosts()
    ip_mapping = {}
    hosts_file = '127.0.0.1 localhost\n'
    for id in generate_homa_cmds.sb_commands:
        ip = str(next(ips))
        ip_mapping[id] = ip
        hosts_file += f'{ip} node{id}\n'

    e = Experiment(name)
    e.checkpoint = False
    sync = True

    HostClass = sims.QemuHost

    net = sims.NS3E2ENet()
    topo = e2e_topologies.HomaTopology(
        n_agg_racks=n_racks,
        h_per_rack=h_per_rack,
        **net_opts
    )
    net.add_component(topo)

    # create simbricks hosts
    for id, commands in generate_homa_cmds.sb_commands.items():
        # create host
        client_config = nc.HomaNode()
        client_config.ip = ip_mapping[id]
        client_config.memory = 2048
        client_config.do_extract_disk = True
        app = HomaApp()
        app.hosts_file = hosts_file
        app.commands = commands
        if 'mtu' in opts:
            client_config.mtu = opts['mtu']
            app.kernel_parameters['.net.homa.max_gso_size'] = opts['mtu']
        client_config.app = app
        client = HostClass(client_config)
        client.sync = sync
        client.name = f'host_node{id}'
        client.wait = True  # wait for client simulator to finish execution
        e.add_host(client)

        # attach client's NIC
        client_nic = sims.I40eNIC()
        client_nic.sync_mode = 1 if sync else 0
        e.add_nic(client_nic)
        client.add_nic(client_nic)

        # attach to network
        topo.add_simbricks_host_r(client_nic)

    e.add_network(net)
    net.init_network()

    experiments.append(e)

base_opts = {
    'no_rtt_files': False,
    'app_time': 8,
    'client_ports': 1,
    'port_receivers': 1,
    'client_max': 100,
    'server_ports': 1,
    'port_threads': 1,
    'tcp_client_ports': 1,
    'tcp_port_receivers': 1,
    'tcp_server_ports': 1,
    'tcp_port_threads': 1,
    'unloaded': 0,
    'no_homa_prio': False,
}

base_unloaded_opts = {
    'no_rtt_files': False,
    'app_time': 15,
    'client_ports': 1,
    'port_receivers': 1,
    'client_max': 1,
    'server_ports': 1,
    'port_threads': 1,
    'tcp_client_ports': 1,
    'tcp_port_receivers': 1,
    'tcp_server_ports': 1,
    'tcp_port_threads': 1,
    'unloaded': 500,
    'no_homa_prio': True,
    'protocol': 'homa',
}

configs = [ # protocol, workload, create unloaded run, mtu
    ['homa', 'w5', True, 4500],
    ['tcp', 'w5', False, 4500],
    ['homa', 'w5', True, 9000],
    ['tcp', 'w5', False, 9000],
]

n_racks = 3
h_per_rack = 4

for p, w, unloaded, mtu in configs:
    opts = base_opts.copy()
    opts['protocol'] = p
    opts['workload'] = w
    opts['mtu'] = mtu
    net_opts = {'mtu': str(mtu)}
    num_nodes = n_racks * h_per_rack
    add_exp(
        f'cluster_{p}_{w}_r{n_racks}_h{h_per_rack}_mtu{mtu}',
        n_racks,
        h_per_rack,
        opts,
        range(num_nodes),
        range(num_nodes),
        net_opts
    )

    if unloaded:
        opts = base_unloaded_opts.copy()
        opts['workload'] = w
        opts['mtu'] = mtu
        add_exp(
            f'cluster_unloaded_{w}_mtu{mtu}',
            2,
            1,
            opts,
            [0],
            [1],
            net_opts
        )
