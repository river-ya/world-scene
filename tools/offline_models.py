"""Resolve the pinned Wan snapshot without modifying upstream model code."""
from contextlib import ExitStack, contextmanager
from functools import wraps
import os
from pathlib import Path

from common import lock


WAN_REPO = 'Wan-AI/Wan2.2-TI2V-5B-Diffusers'


def offline_environment():
    for name in ('TRANSFORMERS_CACHE', 'PYTORCH_TRANSFORMERS_CACHE',
                 'PYTORCH_PRETRAINED_BERT_CACHE'):
        os.environ.pop(name, None)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'


def wan_snapshot(assets):
    spec = next(item for item in lock()['assets'] if item['repo'] == WAN_REPO)
    snapshot = (Path(assets).resolve() / 'hf/hub' /
                ('models--' + WAN_REPO.replace('/', '--')) / 'snapshots' / spec['revision'])
    if not snapshot.is_dir():
        raise FileNotFoundError('缺少锁定的 Wan 本地快照: ' + str(snapshot))
    return snapshot


@contextmanager
def redirect_loader(base, snapshot):
    """Preserve subclass binding and restore the exact descriptor on exit."""
    descriptor = base.__dict__['from_pretrained']
    original = descriptor.__func__

    @wraps(original)
    def local_load(cls, pretrained_model_name_or_path, *args, **kwargs):
        if str(pretrained_model_name_or_path) == WAN_REPO:
            pretrained_model_name_or_path = str(snapshot)
            kwargs['local_files_only'] = True
        return original(cls, pretrained_model_name_or_path, *args, **kwargs)

    base.from_pretrained = classmethod(local_load)
    try:
        yield
    finally:
        base.from_pretrained = descriptor


@contextmanager
def local_wan_loaders(snapshot):
    # Import after offline_environment(), before importing upstream app.py.
    from diffusers.models.modeling_utils import ModelMixin
    from diffusers.schedulers.scheduling_utils import SchedulerMixin
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

    with ExitStack() as stack:
        for base in (ModelMixin, SchedulerMixin, PreTrainedModel, PreTrainedTokenizerBase):
            stack.enter_context(redirect_loader(base, snapshot))
        yield


def preflight(assets):
    """CPU-only tokenizer/config/index checks; never instantiate model weights."""
    offline_environment()
    from assets import verify
    verify(assets, 'models', quick=True)
    snapshot = wan_snapshot(assets)
    from diffusers.configuration_utils import ConfigMixin
    from diffusers.utils.hub_utils import _get_checkpoint_shard_files
    from transformers import T5TokenizerFast

    with local_wan_loaders(snapshot):
        tokenizer = T5TokenizerFast.from_pretrained(WAN_REPO, subfolder='tokenizer')
        if not tokenizer.is_fast or not tokenizer('A living room.')['input_ids']:
            raise RuntimeError('Tokenizer 自检失败')
    class ModelConfig(ConfigMixin):
        config_name = 'config.json'

    class SchedulerConfig(ConfigMixin):
        config_name = 'scheduler_config.json'

    for component in ('vae', 'transformer', 'text_encoder'):
        ModelConfig.load_config(str(snapshot), subfolder=component, local_files_only=True)
    SchedulerConfig.load_config(str(snapshot), subfolder='scheduler', local_files_only=True)
    counts = {}
    for component, index_name in (
        ('transformer', 'diffusion_pytorch_model.safetensors.index.json'),
        ('text_encoder', 'model.safetensors.index.json'),
    ):
        files, _ = _get_checkpoint_shard_files(
            str(snapshot), str(snapshot / component / index_name),
            subfolder=component, local_files_only=True)
        counts[component] = len(files)
    print('OFFLINE_PREFLIGHT_OK', snapshot, counts, flush=True)
    return snapshot
