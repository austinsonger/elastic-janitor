"""
Policy-based actions CLI commands.
"""
import click
from ..utils.decorators import pass_es_client, handle_errors, common_options
from ..utils.output import format_output, OutputFormat, success, error, info
from ...operations.policy_actions import (
    option_policy_list,
    option_policy_create,
    option_policy_evaluate,
    option_policy_delete,
    option_policy_toggle,
)


@click.group(name='policy-actions')
def policy_actions():
    """Policy-based actions (IFTTT rule engine) commands."""
    pass


@policy_actions.command(name='list')
@common_options
@handle_errors
@pass_es_client
def list_policies(es, output, verbose, quiet):
    """
    List all configured automation policies.

    Examples:

        # List policies
        elastic-janitor policy-actions list
    """
    if not quiet:
        info("Listing configured policies...")

    option_policy_list(es)


@policy_actions.command()
@common_options
@handle_errors
@pass_es_client
def create(es, output, verbose, quiet):
    """
    Create a new automation policy from template or custom definition.

    Examples:

        # Create a new policy
        elastic-janitor policy-actions create
    """
    option_policy_create(es)


@policy_actions.command()
@common_options
@handle_errors
@pass_es_client
def evaluate(es, output, verbose, quiet):
    """
    Evaluate all enabled policies against current cluster state.

    Checks conditions and shows which policies would trigger.
    Optionally executes triggered policy actions.

    Examples:

        # Evaluate policies
        elastic-janitor policy-actions evaluate
    """
    if not quiet:
        info("Evaluating policies...")

    option_policy_evaluate(es)


@policy_actions.command()
@common_options
@handle_errors
@pass_es_client
def delete(es, output, verbose, quiet):
    """
    Delete saved policies.

    Examples:

        # Delete policies interactively
        elastic-janitor policy-actions delete
    """
    option_policy_delete(es)


@policy_actions.command()
@common_options
@handle_errors
@pass_es_client
def toggle(es, output, verbose, quiet):
    """
    Enable or disable existing policies.

    Examples:

        # Toggle policy status
        elastic-janitor policy-actions toggle
    """
    option_policy_toggle(es)
