import os
import re
import socket
import time
from datetime import datetime


def get_timestamp(log):
    # Get timestamp from log.
    # Log example:
    # 2021/02/15 12:37:04 wazuh-agentd: INFO: Agent is restarting due to shared configuration changes.
    timestamp = re.search(r'^\d\d\d\d/\d\d/\d\d\s\d\d:\d\d:\d\d', log).group(0)

    t = datetime.strptime(timestamp, "%Y/%m/%d %H:%M:%S")

    return t


def get_agent_health_base(agent_old=False):
    # Get agent health. The agent will be healthy if it has been connected to the manager after been
    # restarted due to shared configuration changes.
    # Using agentd when using grep as the module name can vary between ossec-agentd and wazuh-agentd,
    # depending on the agent version.

    wazuh_log_file = "/var/ossec/logs/wazuh.log" if not agent_old else "/var/ossec/logs/ossec.log"

    shared_conf_restart = os.system(
        f"grep -q 'agentd: INFO: Agent is restarting due to shared configuration changes.' {wazuh_log_file}")
    agent_connection = os.system(
        f"grep -q 'agentd: INFO: (4102): Connected to the server' {wazuh_log_file}")

    if shared_conf_restart == 0 and agent_connection == 0:
        # No -q option as we need the output
        output_agent_restart = os.popen(
            f"grep 'agentd: INFO: Agent is restarting due to shared configuration changes.' "
            f"{wazuh_log_file}").read().split("\n")
        output_agent_connection = os.popen(
            f"grep 'agentd: INFO: (4102): Connected to the server' {wazuh_log_file}").read().split("\n")

        t1 = get_timestamp(output_agent_restart[-2])
        t2 = get_timestamp(output_agent_connection[-2])

        if t2 > t1:
            # Wait to avoid the worst case:
            # +10 seconds for the agent to report the worker
            # +10 seconds for the worker to report master
            # After this time, the agent appears as active in the master node
            time.sleep(20)
            return 0

    return 1


def check(result):
    if result == 0:
        return 0
    else:
        return 1


def get_master_health():
    os.system("/var/ossec/bin/agent_control -ls > /tmp/output.txt")
    os.system("/var/ossec/bin/wazuh-control status > /tmp/daemons.txt")
    check0 = check(os.system("diff -q /tmp/output.txt /tmp/healthcheck/agent_control_check.txt"))
    check1 = check(os.system("diff -q /tmp/daemons.txt /tmp/healthcheck/daemons_check.txt"))
    check2 = check(os.system("grep -qs 'Listening on ' /var/ossec/logs/api.log"))
    return check0 or check1 or check2


def get_worker_health():
    os.system("/var/ossec/bin/wazuh-control status > /tmp/daemons.txt")
    check0 = check(os.system("diff -q /tmp/daemons.txt /tmp/healthcheck/daemons_check.txt"))
    check1 = check(os.system("grep -qs 'Listening on ' /var/ossec/logs/api.log"))
    return check0 or check1


def get_manager_health_base():
    return get_master_health() if socket.gethostname() == 'wazuh-master' else get_worker_health()
