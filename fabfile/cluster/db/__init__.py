from fabric.api import runs_once, settings, task
from fabric.tasks import execute
from .. import hosts as cluster_hosts, util as cluster_util
from ... import db, puppet

__all__ = ["upgrade", "upgrade_host"]


@runs_once
@task
def upgrade():
    """Runs through a general upgrade procedure for a set of Cassandra nodes.

        This will:

            1.  Ask for a password with which to sudo. All servers must have
                the same sudo passowrd
            2.  Perform a git pull on the puppet node to get the latest
                configuration
            3.  Run puppet on each db node
            4.  On each db node sequentially:
                    a. Run nodetool drain
                    b. Restart dse
                    c. Run nodetool upgradesstables
    """
    cluster_util.ensure_sudo_pass()

    # Stop puppet on the db nodes
    with settings(hosts=cluster_hosts.db(), parallel=True):
        execute(puppet.stop, force=True)

    # Pull the updated puppet configuration
    with settings(hosts=[cluster_hosts.puppet()], parallel=True):
        execute(puppet.git_update)

    # Run puppet on the db nodes
    with settings(hosts=cluster_hosts.db(), parallel=True):
        execute(puppet.run, force=False)

    # Upgrade each db node sequentially
    with settings(hosts=cluster_hosts.db(), parallel=False):
        execute(upgrade_host_internal)

    # Start puppet on the db nodes
    with settings(hosts=cluster_hosts.db(), parallel=True):
        execute(puppet.start)


@runs_once
@task
def upgrade_host():
    """Run through the general upgrade procedure for a Cassandra node, assuming
    puppet has already been updated.

        This will:

            1.  Ask for a password with which to sudo
            2.  Forcefully stop any current puppet runs
            3.  Run puppet on the node
            4.  Run nodetool drain
            5.  Restart dse
            6.  Run nodetool upgradesstables
    """
    cluster_util.ensure_sudo_pass()

    execute(puppet.stop, force=True)
    execute(puppet.run, force=False)
    execute(upgrade_host_internal)
    execute(puppet.start)


def upgrade_host_internal():
    db.drain()
    db.stop()
    db.start()
    db.wait_until_ready()
    db.upgradesstables()