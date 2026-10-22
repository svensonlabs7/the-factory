"""Helm packages Kubernetes manifests as a versioned CHART: templates + a values file, rendered into manifests,
installed as a tracked RELEASE you can upgrade and roll back. The templates produce YAML by STRING substitution,
and YAML is whitespace-significant -- so the classic Helm footgun is an indentation bug that renders structurally
wrong (or invalid) YAML. `helm template` / `helm lint` render and parse locally, catching it before `helm install`
ever reaches the cluster; a blind apply ships the broken manifest.

A. A chart template injecting a map of labels. With correct indentation the manifest parses to the intended
   structure; with the wrong indentation it parses to the WRONG structure (labels land under the apiVersion line
   / collapse), which only a render-and-validate step catches.
Run: uv run --with pyyaml python 106_helm.py. No cluster."""
import yaml

values = {"name": "factory", "labels": {"app": "factory", "tier": "web"}}


def render(indent):
    """A tiny Helm-style template. `indent` is the leading spaces applied to the injected labels block."""
    labels_block = yaml.safe_dump(values["labels"], default_flow_style=False).strip()
    labels_block = "\n".join(" " * indent + line for line in labels_block.splitlines())
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {values['name']}
  labels:
{labels_block}
"""


def check(label, text):
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(f"{label}: INVALID YAML -> {str(e).splitlines()[0]}")
        return
    labels = (doc.get("metadata") or {}).get("labels")
    ok = labels == values["labels"]
    print(f"{label}: parsed metadata.labels = {labels!r}  -> {'correct' if ok else 'WRONG STRUCTURE'}")


print("A  render the labels block at different indentation, then render-and-validate (what `helm template` does):")
# metadata.labels children must be indented 4 spaces (2 for metadata, 2 more for labels' keys).
check("   indent=4 (correct)", render(4))
check("   indent=2 (bug)    ", render(2))

print("\nB  what each workflow would do with the indent=2 chart:")
bad = render(2)
try:
    doc = yaml.safe_load(bad)
    mislabeled = (doc.get("metadata") or {}).get("labels") != values["labels"]
    print(f"   helm template/lint: renders locally, parse shows labels wrong={mislabeled} -> caught before install")
except yaml.YAMLError:
    print("   helm template/lint: parse error -> caught before install")
print("   blind kubectl apply of the rendered text: ships the mis-structured Deployment to the cluster")
