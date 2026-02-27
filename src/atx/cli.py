from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional

import click

from .config import STACKS
from .executil import exec_cmd, eprint, has_cmd
from .stacks import discover_stacks, expand_stack, pick_stack_fzf


class MutuallyExclusiveOption(click.Option):
    """
    A Click Option that cannot be used with one or more other options.

    Usage:
      click.option(..., cls=MutuallyExclusiveOption, mutually_exclusive=["other_opt", ...])
    Where the values in mutually_exclusive are the *parameter names* (not flags).
    """

    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.name in opts and self.mutually_exclusive.intersection(opts):
            others = ", ".join(f"--{n.replace('_', '-')}" for n in sorted(self.mutually_exclusive))
            raise click.UsageError(
                f"Illegal usage: --{self.name.replace('_', '-')} cannot be used with {others}.",
                ctx=ctx,
            )
        return super().handle_parse_result(ctx, opts, args)


def _supported_shells() -> List[str]:
    return ["bash", "zsh", "fish"]


def _generate_completion_script(prog_name: str, shell: str) -> str:
    try:
        from click.shell_completion import get_completion_script  # Click 8+
    except Exception as e:
        raise click.ClickException(
            "Your installed 'click' version does not support shell completion. "
            "Upgrade with: pip install -U click"
        ) from e

    if shell not in _supported_shells():
        raise click.ClickException(f"Unsupported shell '{shell}'. Use one of: {', '.join(_supported_shells())}")

    return get_completion_script(prog_name, shell)


def _completion_install_path(shell: str) -> Path:
    base = Path.home() / ".config" / "atx"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"completion.{shell}"


def _find_workflow_file(workflow_name: str) -> Optional[str]:
    """
    Find which workflow file contains the given workflow name.
    Returns the file name (without .yaml extension) or None if not found.
    """
    import os
    import subprocess
    
    # Get workflow base path from env or use default
    base_path = os.environ.get("ATMOS_WORKFLOWS_BASE_PATH", "stacks/workflows")
    
    # Try to find the workflow file by searching for the workflow name
    # We look for lines like "  workflow_name:" (2 spaces, then the name, then colon)
    if not os.path.isdir(base_path):
        return None
    
    for yaml_file in Path(base_path).glob("*.yaml"):
        if yaml_file.name == "README.yaml":
            continue
        
        try:
            # Use grep/awk to find if this file contains the workflow
            # Look for pattern: ^  workflow_name: (exactly 2 spaces, workflow name, colon)
            result = subprocess.run(
                ["grep", "-q", f"^  {workflow_name}:", str(yaml_file)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                # Return filename without .yaml extension
                return yaml_file.stem
        except (subprocess.SubprocessError, FileNotFoundError):
            # If grep is not available, fall back to reading the file
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    in_workflows = False
                    for line in f:
                        if line.strip() == "workflows:":
                            in_workflows = True
                            continue
                        if in_workflows:
                            # Check if this is a top-level workflow (2 spaces indent)
                            if line.startswith(f"  {workflow_name}:"):
                                return yaml_file.stem
                            # If we hit a non-indented line, we're out of workflows section
                            if line and not line.startswith(" ") and not line.startswith("#"):
                                break
            except (IOError, OSError):
                continue
    
    return None


EPILOG = """\
Examples:

  Terraform plan:
    atx -p sb eks/karpenter

  Terraform apply with auto-approve:
    atx -a -auto prod vpc

  Terraform destroy with explicit -s:
    atx -d -auto -s stage rds

  Terraform clean:
    atx -c sb eks/cluster

  List stacks (best-effort):
    atx -l

  Atmos workflow mode:
    atx -w create-platform-cluster -f eks-cluster -s sb

Shell completion:

  Install completion script:
    atx --install-completion bash
    atx --install-completion zsh
    atx --install-completion fish

  Show completion script:
    atx --show-completion bash
"""


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
        help_option_names=["-h", "--help"],  # -h alias
    ),
    epilog=EPILOG,
)
@click.option(
    "-p",
    "--plan",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["apply_", "destroy", "clean"],
    help="terraform plan",
)
@click.option(
    "-a",
    "--apply",
    "apply_",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["plan", "destroy", "clean"],
    help="terraform apply",
)
@click.option(
    "-d",
    "--destroy",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["plan", "apply_", "clean"],
    help="terraform destroy",
)
@click.option(
    "-c",
    "--clean",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["plan", "apply_", "destroy"],
    help="terraform clean",
)
@click.option("-auto", "auto_approve", is_flag=True, help="Add --auto-approve (apply/destroy only)")
@click.option("-w", "--workflow", is_flag=True, help="Use atmos workflow instead of terraform")
@click.option("-l", "-list", "list_", is_flag=True, help="List stacks (best-effort via `atmos describe stacks`)")
@click.option("-s", "--stack", type=str, default=None, help="Stack alias or full stack name")
@click.option(
    "--show-completion",
    type=click.Choice(_supported_shells()),
    help="Print shell completion script and exit",
)
@click.option(
    "--install-completion",
    type=click.Choice(_supported_shells()),
    help="Install shell completion script under ~/.config/atx/",
)
@click.pass_context
def main(
    ctx: click.Context,
    plan: bool,
    apply_: bool,
    destroy: bool,
    clean: bool,
    auto_approve: bool,
    workflow: bool,
    list_: bool,
    stack: Optional[str],
    show_completion: Optional[str],
    install_completion: Optional[str],
) -> None:
    # --- completion helpers (must run before requiring atmos) ---
    if show_completion:
        script = _generate_completion_script(ctx.info_name or "atx", show_completion)
        click.echo(script)
        raise SystemExit(0)

    if install_completion:
        script = _generate_completion_script(ctx.info_name or "atx", install_completion)
        out_path = _completion_install_path(install_completion)
        out_path.write_text(script, encoding="utf-8")

        click.echo(f"Wrote completion script to: {out_path}\n")
        if install_completion == "bash":
            click.echo(f'Add to ~/.bashrc:\n  source "{out_path}"')
        elif install_completion == "zsh":
            click.echo(f'Add to ~/.zshrc:\n  source "{out_path}"')
        else:
            click.echo(f'Add to ~/.config/fish/config.fish:\n  source "{out_path}"')
        raise SystemExit(0)

    extra_args: List[str] = list(ctx.args)

    # --- list stacks ---
    if list_:
        # Always show aliases first (never empty), then discovered stacks
        for k, v in sorted(STACKS.items()):
            click.echo(f"{k} -> {v}")
        for s in discover_stacks(verbose_errors=True):
            click.echo(s)
        raise SystemExit(0)

    if not has_cmd("atmos"):
        raise click.ClickException("atmos not found in PATH")

    # --- workflow mode ---
    if workflow:
        # Resolve stack alias if -s/--stack was provided via click option
        workflow_args: List[str] = list(extra_args)
        
        # Auto-detect workflow file if -f/--file is not already specified
        has_file_flag = False
        workflow_name: Optional[str] = None
        
        # Check if -f/--file is already in args
        for i, arg in enumerate(workflow_args):
            if arg in ("-f", "--file"):
                has_file_flag = True
                break
            # First non-flag arg is likely the workflow name
            if arg and not arg.startswith("-") and workflow_name is None:
                workflow_name = arg
        
        # If no -f flag and we have a workflow name, try to find the file
        if not has_file_flag and workflow_name:
            workflow_file = _find_workflow_file(workflow_name)
            if workflow_file:
                # Insert -f and file after the workflow name
                # Find the index of the workflow name
                try:
                    name_idx = workflow_args.index(workflow_name)
                    workflow_args.insert(name_idx + 1, "-f")
                    workflow_args.insert(name_idx + 2, workflow_file)
                except ValueError:
                    # Fallback: append if we can't find it
                    workflow_args.extend(["-f", workflow_file])
        
        if stack:
            resolved_stack = expand_stack(stack)
            # Append -s and resolved stack at the end
            # Final command format: atmos workflow <workflow-name> -f <file> -s <stack>
            workflow_args.extend(["-s", resolved_stack])
        
        cmd = ["atmos", "workflow", *workflow_args]
        exec_cmd(cmd)

    # --- require exactly one action ---
    if (plan + apply_ + destroy + clean) != 1:
        raise click.UsageError("You must specify exactly one action: -p/--plan, -a/--apply, -d/--destroy, or -c/--clean.", ctx=ctx)

    action = "plan" if plan else "apply" if apply_ else "destroy" if destroy else "clean"

    # --- resolve stack ---
    resolved_stack: Optional[str] = None

    if stack:
        resolved_stack = expand_stack(stack)
    else:
        # bare alias detection; remove the alias token from forwarded args
        for idx, arg in enumerate(list(extra_args)):
            if arg in STACKS:
                resolved_stack = STACKS[arg]
                del extra_args[idx]
                break

    if not resolved_stack:
        try:
            resolved_stack = pick_stack_fzf()
        except RuntimeError as e:
            raise click.ClickException(str(e))

    if not extra_args:
        raise click.UsageError("Missing component.", ctx=ctx)

    # --- auto approve ---
    tf_extra: List[str] = []
    if auto_approve:
        if action in ("apply", "destroy"):
            tf_extra.append("--auto-approve")
        else:
            click.echo("⚠️  -auto is ignored for 'plan'", err=True)

    # --- Special handling for eks/karpenter ---
    # Due to Terraform Kubernetes provider limitations, Karpenter requires a two-phase deployment:
    # 1. Install CRDs first (targeted apply)
    # 2. Then install Karpenter and create manifests (full apply)
    # The second phase must use --auto-approve to skip plan validation, which fails because
    # the provider validates CRD schemas during plan before resources are created.
    component = extra_args[0] if extra_args else None
    is_karpenter = component and component in ("eks/karpenter", "karpenter")
    
    if is_karpenter and action == "apply":
        # Phase 1: Apply CRD resources first
        click.echo("Phase 1: Installing Karpenter CRDs...")
        crd_targets = [
            "-target=helm_release.karpenter_crd",
            "-target=null_resource.wait_for_karpenter_crds",
            "-target=time_sleep.wait_for_crd_propagation",
        ]
        # Use auto-approve for the targeted CRD apply
        cmd_phase1 = ["atmos", "terraform", "apply", "-s", resolved_stack, component, *crd_targets, "--auto-approve"]
        eprint("▶ " + " ".join(cmd_phase1))
        result1 = subprocess.run(cmd_phase1, check=False)
        if result1.returncode != 0:
            raise click.ClickException(f"Phase 1 (CRD installation) failed with exit code {result1.returncode}")
        
        # Phase 2: Apply the full component
        # We need to skip the plan phase because it validates CRD schemas before apply
        # Even though CRDs are installed, the provider may not have refreshed its schema yet
        # So we generate varfile/backend and run terraform apply directly to skip plan
        click.echo("\nPhase 2: Installing Karpenter and creating manifests...")
        # Determine component directory path
        component_dir = f"components/terraform/{component}"
        repo_root = os.getcwd()
        component_path = os.path.join(repo_root, component_dir)
        
        # Generate varfile and backend configuration first
        # The varfile will be generated in the component directory
        click.echo("Generating Terraform configuration files...")
        
        # Generate varfile in the component directory (atmos generates it there by default)
        varfile_name = "terraform.auto.tfvars.json"
        varfile_relative = os.path.join(component_dir, varfile_name)
        cmd_varfile = ["atmos", "terraform", "generate", "varfile", component, "-s", resolved_stack, "-f", varfile_relative]
        varfile_result = subprocess.run(cmd_varfile, check=False, cwd=repo_root, capture_output=True, text=True)
        if varfile_result.returncode != 0:
            eprint(f"Warning: Varfile generation had issues: {varfile_result.stderr}")
            # Try without explicit path (atmos might generate it in component dir by default)
            cmd_varfile2 = ["atmos", "terraform", "generate", "varfile", component, "-s", resolved_stack]
            subprocess.run(cmd_varfile2, check=False, cwd=repo_root)
        
        cmd_backend = ["atmos", "terraform", "generate", "backend", component, "-s", resolved_stack]
        backend_result = subprocess.run(cmd_backend, check=False, cwd=repo_root, capture_output=True, text=True)
        if backend_result.returncode != 0:
            eprint(f"Warning: Backend generation had issues: {backend_result.stderr}")
        
        # Verify varfile exists (try multiple possible locations/names)
        varfile_to_use = None
        possible_varfiles = [
            os.path.join(component_path, "terraform.auto.tfvars.json"),
            os.path.join(component_path, "terraform.tfvars.json"),
        ]
        for vf in possible_varfiles:
            if os.path.exists(vf):
                varfile_to_use = os.path.basename(vf)
                eprint(f"Found varfile: {varfile_to_use}")
                break
        
        # Then run terraform apply directly (bypassing plan phase)
        # This skips the plan validation that would fail
        # Use -var-file if we found a varfile, otherwise terraform should auto-discover it
        if varfile_to_use:
            shell_cmd = f"cd {component_path} && atmos terraform workspace {component} -s {resolved_stack} && terraform apply -var-file={varfile_to_use} -auto-approve"
        else:
            eprint("Warning: No varfile found, terraform may prompt for variables")
            shell_cmd = f"cd {component_path} && atmos terraform workspace {component} -s {resolved_stack} && terraform apply -auto-approve"
        eprint(f"▶ {shell_cmd}")
        result2 = subprocess.run(["bash", "-c", shell_cmd], check=False)
        if result2.returncode != 0:
            raise click.ClickException(f"Phase 2 (Karpenter installation) failed with exit code {result2.returncode}")
    else:
        # Normal execution for all other components
        cmd = ["atmos", "terraform", action, "-s", resolved_stack, *extra_args, *tf_extra]
        exec_cmd(cmd)
