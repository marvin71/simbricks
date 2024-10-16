#!/usr/bin/python3

# Copyright (c) 2020-2023 Homa Developers
# SPDX-License-Identifier: BSD-1-Clause

# This file contains library functions used to run cluster performance
# tests for the Linux kernel implementation of Homa.

import argparse

# If a server's id appears as a key in this dictionary, it means we
# have started cp_node running on that node. The value of each entry is
# a Popen object that can be used to communicate with the node.
active_nodes = {}

# If a server's id appears as a key in this dictionary, it means we
# have started homa_prio running on that node. The value of each entry is
# a Popen object for the homa_prio instance; if this is terminated, then
# the homa_prio process will end
homa_prios = {}

# The range of nodes currently running cp_node servers.
server_nodes = range(0,0)

# Directory containing log files.
log_dir = ''

# Indicates whether we should generate additional log messages for debugging
verbose = False

# Defaults for command-line options; assumes that servers and clients
# share nodes.
default_defaults = {
    'gbps':                0.0,
    # Note: very large numbers for client_max hurt Homa throughput with
    # unlimited load (throttle queue inserts take a long time).
    'client_max':          200,
    'client_ports':        3,
    'log_dir':             '/data/data/',
    'no_trunc':            '',
    'protocol':            'homa',
    'port_receivers':      3,
    'port_threads':        3,
    'seconds':             30,
    'server_ports':        3,
    'tcp_client_ports':    4,
    'tcp_port_receivers':  1,
    'tcp_server_ports':    8,
    'tcp_port_threads':    1,
    'unloaded':            0,
    'unsched':             0,
    'unsched_boost':       0.0,
    'workload':            ''
}

# Default bandwidths to use when running all of the workloads.
load_info = [["w1", 1.4], ["w2", 3.2], ["w3", 14], ["w4", 20], ["w5", 20]]

sb_commands = {}

def boolean(s):
    """
    Used as a "type" in argparse specs; accepts Boolean-looking things.
    """
    map = {'true': True, 'yes': True, 'ok': True, "1": True, 'y': True,
        't': True, 'false': False, 'no': False, '0': False, 'f': False,
        'n': False}
    lc = s.lower()
    if lc not in map:
        raise ValueError("Expected boolean value, got %s" % (s))
    return map[lc]

def print_sb_commands():
    global sb_commands
    for id, cmds in sb_commands.items():
        print(f"commands for node{id}")
        print("[")
        for cmd in cmds:
            print(f"    \"{cmd}\",")
        print("]")

def get_parser(defaults = {}):
    """
    Returns an ArgumentParser for options that are commonly used in
    performance tests.

    description:    A string describing the overall functionality of this
                    particular performance test
    usage:          A command synopsis (passed as usage to ArgumentParser)
    defaults:       A dictionary whose keys are option names and whose values
                    are defaults; used to modify the defaults for some of the
                    options (there is a default default for each option).
    """
    for key in default_defaults:
        if not key in defaults:
            defaults[key] = default_defaults[key]
    parser = argparse.ArgumentParser(description='The options '
            'below may include some that are not used by this particular '
            'benchmark', add_help=False,
            conflict_handler='resolve')
    parser.add_argument('-b', '--gbps', type=float, dest='gbps',
            metavar='B', default=defaults['gbps'],
            help='Generate a total of B Gbits/sec of bandwidth on the most '
            'heavily loaded machines; 0 means run as fast as possible '
            '(default: %.2f)' % (defaults['gbps']))
    parser.add_argument('--client-max', type=int, dest='client_max',
            metavar='count', default=defaults['client_max'],
            help='Maximum number of requests each client machine can have '
            'outstanding at a time (divided evenly among its ports) '
            '(default: %d)' % (defaults['client_max']))
    parser.add_argument('--client-ports', type=int, dest='client_ports',
            metavar='count', default=defaults['client_ports'],
            help='Number of ports on which each client should issue requests '
            '(default: %d)' % (defaults['client_ports']))
    parser.add_argument('--cperf-log', dest='cperf_log',
            metavar='F', default='cperf.log',
            help='Name to use for the cperf log file (default: cperf.log)')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
            help='Pause after starting servers to enable debugging setup')
    parser.add_argument('-h', '--help', action='help',
            help='Show this help message and exit')
    parser.add_argument('-6', '--ipv6', dest='ipv6', action='store_const',
            const='--ipv6', default='',
            help='Use IPv6 for communication (default: use IPv4)')
    parser.add_argument('-l', '--log-dir', dest='log_dir',
            metavar='D', default=defaults['log_dir'],
            help='Directory to use for logs and metrics')
    parser.add_argument('-n', '--nodes', type=int, dest='num_nodes',
            metavar='N', help='Total number of nodes to use in the cluster')
    parser.add_argument('--no-homa-prio', dest='no_homa_prio',
            action='store_true', default=False,
            help='Don\'t run homa_prio on nodes to adjust unscheduled cutoffs')
    parser.add_argument('--plot-only', dest='plot_only', action='store_true',
            help='Don\'t run experiments; generate plot(s) with existing data')
    parser.add_argument('--port-receivers', type=int, dest='port_receivers',
            metavar='count', default=defaults['port_receivers'],
            help='Number of threads listening for responses on each Homa '
            'client port (default: %d)'% (defaults['port_receivers']))
    parser.add_argument('--port-threads', type=int, dest='port_threads',
            metavar='count', default=defaults['port_threads'],
            help='Number of threads listening on each Homa server port '
            '(default: %d)'% (defaults['port_threads']))
    parser.add_argument('-p', '--protocol', dest='protocol',
            choices=['homa', 'tcp', 'dctcp'], default=defaults['protocol'],
            help='Transport protocol to use (default: %s)'
            % (defaults['protocol']))
    parser.add_argument('-s', '--seconds', type=int, dest='seconds',
            metavar='S', default=defaults['seconds'],
            help='Run each experiment for S seconds (default: %.1f)'
            % (defaults['seconds']))
    parser.add_argument('--server-ports', type=int, dest='server_ports',
            metavar='count', default=defaults['server_ports'],
            help='Number of ports on which each server should listen '
            '(default: %d)'% (defaults['server_ports']))
    parser.add_argument('--set-ids', dest='set_ids', type=boolean,
            default=True, metavar="T/F", help="Boolean value: if true, the "
            "next_id sysctl parameter will be set on each node in order to "
            "avoid conflicting RPC ids on different nodes (default: true)")
    parser.add_argument('--skip', dest='skip',
            metavar='nodes',
            help='List of node numbers not to use in the experiment; can '
            ' contain ranges, such as "3,5-8,12"')
    parser.add_argument('--tcp-client-ports', type=int, dest='tcp_client_ports',
            metavar='count', default=defaults['tcp_client_ports'],
            help='Number of ports on which each TCP client should issue requests '
            '(default: %d)'% (defaults['tcp_client_ports']))
    parser.add_argument('--tcp-port-receivers', type=int,
            dest='tcp_port_receivers', metavar='count',
            default=defaults['tcp_port_receivers'],
            help='Number of threads listening for responses on each TCP client '
            'port (default: %d)'% (defaults['tcp_port_receivers']))
    parser.add_argument('--tcp-port-threads', type=int, dest='tcp_port_threads',
            metavar='count', default=defaults['tcp_port_threads'],
            help='Number of threads listening on each TCP server port '
            '(default: %d)'% (defaults['tcp_port_threads']))
    parser.add_argument('--tcp-server-ports', type=int, dest='tcp_server_ports',
            metavar='count', default=defaults['tcp_server_ports'],
            help='Number of ports on which TCP servers should listen '
            '(default: %d)'% (defaults['tcp_server_ports']))
    parser.add_argument('--tt-freeze', dest='tt_freeze', type=boolean,
            default=True, metavar="T/F", help="Boolean value: if true, "
            "timetraces will be frozen on all nodes at the end of the "
            "Homa benchmark run (default: false)")
    parser.add_argument('--unsched', type=int, dest='unsched',
            metavar='count', default=defaults['unsched'],
            help='If nonzero, homa_prio will always use this number of '
            'unscheduled priorities, rather than computing from workload'
            '(default: %d)'% (defaults['unsched']))
    parser.add_argument('--unsched-boost', type=float, dest='unsched_boost',
            metavar='float', default=defaults['unsched'],
            help='Increase the number of unscheduled priorities that homa_prio '
            'assigns by this (possibly fractional) amount (default: %.2f)'
            % (defaults['unsched_boost']))
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
            help='Enable verbose output in node logs')
    parser.add_argument('-w', '--workload', dest='workload',
            metavar='W', default=defaults['workload'],
            help='Workload to use for benchmark: w1-w5 or number, empty '
            'means try each of w1-w5 (default: %s)'
            % (defaults['workload']))
    return parser

def init(options):
    """
    Initialize various global state, such as the log file.
    """
    global log_dir, verbose, sb_commands, active_nodes, homa_prios, server_nodes
    log_dir = options.log_dir
    verbose = options.verbose
    
    active_nodes = {}
    homa_prios = {}
    server_nodes = range(0,0)
    sb_commands = {}

    # Figure out which nodes to use for the experiment
    skips = {}
    if options.skip:
        for spec in options.skip.split(","):
            nodes = spec.split("-")
            if len(nodes) == 1:
                skips[int(spec)] = 1
            elif len(nodes) == 2:
                for i in range(int(nodes[0]), int(nodes[1])+1):
                    skips[i] = 1
            else:
                raise Exception("Bad skip range '%s': must be either id "
                       "or id1-id2" % (spec))
    nodes = []
    id = 0
    while len(nodes) != options.num_nodes:
        if not id in skips:
            nodes.append(id)
            sb_commands[id] = [
                'cp /tmp/guest/hosts /etc/hosts',
                'mkfifo input_pipe',
                'exec 3<> input_pipe',
            ]
        id += 1
    options.nodes = nodes
    options.servers = options.nodes
    options.clients = options.nodes

    for param in ['dead_buffs_limit', 'grant_fifo_fraction',
            'gro_policy', 'link_mbps', 'max_dead_buffs',
            'max_grantable_rpcs', 'max_gro_skbs', 'max_gso_size',
            'max_nic_queue_ns', 'max_incoming', 'max_overcommit',
            'max_rpcs_per_peer', 'num_priorities', 'pacer_fifo_fraction',
            'poll_usecs', 'reap_limit', 'resend_interval', 'resend_ticks',
            'throttle_min_bytes', 'timeout_resends', 'unsched_bytes', 'window']:
        for id in nodes:
            sb_commands[id].append(f"sysctl .net.homa.{param}")

def start_nodes(ids, options):
    """
    Start up cp_node on a group of nodes.

    ids:      List of node ids on which to start cp_node, if it isn't already
              running
    options:  Command-line options that may affect experiment
    """
    global active_nodes, sb_commands
    started = []
    for id in ids:
        if id in active_nodes:
            continue
        sb_commands[id].append('/tmp/guest/cp_node < input_pipe &')
        active_nodes[id] = None
        if not options.no_homa_prio:
            homa_prios[id] = None
            sb_commands[id].append(f"/tmp/guest/homa_prio --interval 500 "
                                   f"--unsched {options.unsched} "
                                   f"--unsched-boost {options.unsched_boost} "
                                   f"--log-file {log_dir}/homa_prio-{id}.log &")
        if options.set_ids:
            set_sysctl_parameter(".net.homa.next_id", str(100000000*(id+1)),
                    [id])
        started.append(id)
    #wait_output("% ", started, "ssh")
    log_level = "normal"
    if verbose:
        log_level = "verbose"
    command = f"log --file {log_dir}/node.log --level {log_level}"
    for id in started:
        sb_commands[id].append(f"echo \"{command}\" > input_pipe")
    #wait_output("% ", started, command)

def stop_nodes():
    """
    Exit all of the nodes that are currently active.
    """
    global active_nodes, server_nodes, sb_commands
    for id in homa_prios:
        sb_commands[id].append("pkill homa_prio")
    for id in active_nodes:
        #sb_commands[id].append("echo \"exit\" > input_pipe")
        sb_commands[id].append("exec 3>&-")
        #sb_commands[id].append("wait")
        sb_commands[id].append("sleep 2 # wait for cp_node to exit")
        sb_commands[id].append("sync")
    active_nodes.clear()
    server_nodes = range(0,0)

def do_cmd(command, ids, ids2 = []):
    """
    Execute a cp_node command on a given group of nodes.

    command:    A command to execute on each node
    ids:        List of node ids on which to run the command
    ids2:       An optional additional list of node ids on which to run the
                command; if a node is present in both r and r2, the
                command will only be performed once
    """
    global active_nodes, sb_commands
    nodes = []
    for id in ids:
        nodes.append(id)
    for id in ids2:
        if id not in ids:
            nodes.append(id)
    for id in nodes:
        sb_commands[id].append(f"echo \"{command}\" > input_pipe")
    #wait_output("% ", nodes, command)

def do_ssh(command, nodes):
    """
    Use ssh to execute a particular shell command on a group of nodes.

    command:  command to execute on each node (a list of argument words)
    nodes:    specifies ids of the nodes on which to execute the command:
              should be a range, list, or other object that supports "in"
    """
    global sb_commands
    for id in nodes:
        sb_commands[id].append(" ".join(command))

def get_sysctl_parameter(name):
    """
    Retrieve the value of a particular system parameter using sysctl on
    the current host, and return the value as a string.

    name:      name of the desired configuration parameter
    """
    global sb_commands
    for id in active_nodes:
        sb_commands[id].append(f"sysctl {name}")

def set_sysctl_parameter(name, value, nodes):
    """
    Modify the value of a system parameter on a group of nodes.

    name:     name of the sysctl configuration parameter to modify
    value:    desired value for the parameter
    nodes:    specifies ids of the nodes on which to execute the command:
              should be a range, list, or other object that supports "in"
    """
    global sb_commands
    for id in nodes:
        sb_commands[id].append(f"sysctl {name}={value}")

def start_servers(ids, options):
    """
    Starts cp_node servers running on a group of nodes

    ids:     A list of node ids on which to start cp_node servers
    options: A namespace that must contain at least the following
             keys, which will be used to configure the servers:
                 server_ports
                 port_threads
                 protocol
    """
    global server_nodes, sb_commands
    if len(server_nodes) > 0:
        do_cmd("stop servers", server_nodes)
        server_nodes = []
    start_nodes(ids, options)
    if options.protocol == "homa":
        do_cmd("server --ports %d --port-threads %d --protocol %s %s" % (
                options.server_ports, options.port_threads,
                options.protocol, options.ipv6), ids)
    else:
        do_cmd("server --ports %d --port-threads %d --protocol %s %s" % (
                options.tcp_server_ports, options.tcp_port_threads,
                options.protocol, options.ipv6), ids)
    server_nodes = ids
    for cmds in sb_commands.values():
        cmds.append('sleep 1 # wait for servers to start')

def run_experiment(name, clients, options):
    """
    Starts cp_node clients running on a group of nodes, lets the clients run
    for an amount of time given by options.seconds, and gathers statistics.

    name:     Identifier for this experiment, which is used in the names
              of files created in the log directory.
    clients:  List of node numbers on which to run clients
    options:  A namespace that must contain at least the following attributes,
              which control the experiment:
                  client_max
                  client_ports
                  gbps
                  port_receivers
                  protocol
                  seconds
                  server_ports
                  servers
                  tcp_client_ports
                  tcp_server_ports
                  workload
    """

    global active_nodes, sb_commands
    exp_nodes = list(set(options.servers + list(clients)))
    start_nodes(clients, options)
    nodes = []
    for id in clients:
        if options.protocol == "homa":
            command = "client --ports %d --port-receivers %d --server-ports %d " \
                    "--workload %s --servers %s --gbps %.3f --client-max %d " \
                    "--protocol %s --id %d %s" % (
                    options.client_ports,
                    options.port_receivers,
                    options.server_ports,
                    options.workload,
                    ",".join([str(x) for x in options.servers]),
                    options.gbps,
                    options.client_max,
                    options.protocol,
                    id,
                    options.ipv6)
            if "unloaded" in options:
                command += " --unloaded %d" % (options.unloaded)
        else:
            if "no_trunc" in options:
                trunc = '--no-trunc'
            else:
                trunc = ''
            command = "client --ports %d --port-receivers %d --server-ports %d " \
                    "--workload %s --servers %s --gbps %.3f %s --client-max %d " \
                    "--protocol %s --id %d %s" % (
                    options.tcp_client_ports,
                    options.tcp_port_receivers,
                    options.tcp_server_ports,
                    options.workload,
                    ",".join([str(x) for x in options.servers]),
                    options.gbps,
                    trunc,
                    options.client_max,
                    options.protocol,
                    id,
                    options.ipv6)
        sb_commands[id].append(f"echo \"{command}\" > input_pipe")
        nodes.append(id)
    #wait_output("% ", nodes, command, 40.0)
    if not "unloaded" in options:
        if options.protocol == "homa":
            # Wait a bit so that homa_prio can set priorities appropriately
            for id in exp_nodes:
                sb_commands[id].append("sleep 2 # wait for homa_prio to set prios")
                sb_commands[id].append("cp /proc/net/homa_metrics /data/data/metrics1.txt")
        if not options.no_rtt_files:
            do_cmd("dump_times /dev/null", clients)
        do_cmd("log Starting %s experiment" % (name), server_nodes, clients)
        debug_delay = 0
        if debug_delay > 0:
            for id in exp_nodes:
                sb_commands[id].append(f"sleep {debug_delay} #debug delay")
        if False and "dctcp" in name:
            log("Setting debug info")
            do_cmd("debug 2000 3000", clients)
            log("Finished setting debug info")
        for id in exp_nodes:
            sb_commands[id].append(f"sleep {options.seconds - debug_delay} # wait for experiment to run")
        if options.protocol == "homa" and options.tt_freeze:
            set_sysctl_parameter(".net.homa.action", "7", nodes[0:1])
        do_cmd("log Ending %s experiment" % (name), server_nodes, clients)
    else:
        for id in exp_nodes:
            sb_commands[id].append(f"sleep {options.seconds} # wait for experiment to run")
    if not options.no_rtt_files:
        do_cmd("dump_times /data/data/rtts", clients)
    if (options.protocol == "homa") and not "unloaded" in options:
        for id in exp_nodes:
            sb_commands[id].append("cp /proc/net/homa_metrics /data/data/metrics2.txt")
    if False and "dctcp" in name:
        do_cmd("tt print cp.tt", clients)
    # do_ssh(["sudo", "sysctl", ".net.homa.log_topic=3"], clients)
    # do_ssh(["sudo", "sysctl", ".net.homa.log_topic=2"], clients)
    # do_ssh(["sudo", "sysctl", ".net.homa.log_topic=1"], clients)
    do_cmd("stop clients", clients)
    for id in exp_nodes:
        sb_commands[id].append("sleep 1 # wait for clients to stop")
