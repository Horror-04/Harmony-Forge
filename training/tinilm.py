"""Shared tiny decoder-only transformer (Phase 2 Task 3, R3).

Arch: token emb (256 x 128) + learned pos emb (1024 x 128) + learned
slot emb (7 x 128: position-0 count head + 6 note slots) + 4 x pre-norm
decoder blocks (4-head causal attn, ff 256) + final norm + LM head.
~0.73 M params (budget <= ~2 M). VOCAB=256 covers every flat codec id.
Context cap 1024 tokens / 16 bars (same caps as the C++ codec).

The slot embedding is the phase signal: the flat codec packs heterogeneous
slots (Bar/Subbeat/TrackType/Pitch/Duration/VelocityBin) whose valid ranges
differ per position-in-note. Without it (first training attempt, 60 epochs)
greedy generation drifted out of 6-phase mid-continuation (pitch values in
the Subbeat slot, ...) and 15/33 val continuations failed strict decode.
With it, continuations stay in phase and decode.

Used by train.py (training) and export_onnx.py (ONNX export). The state_dict
key layout is frozen by checkpoints/best.pt — do not rename submodules.
"""

from __future__ import annotations

VOCAB = 256
D_MODEL = 128
N_LAYER = 4
N_HEAD = 4
D_FF = 256
CTX = 1024

CONFIG = {"vocab": VOCAB, "d_model": D_MODEL, "n_layer": N_LAYER,
          "n_head": N_HEAD, "d_ff": D_FF, "ctx": CTX}


def build_model():
    import math

    import torch
    import torch.nn as nn

    HEAD_DIM = D_MODEL // N_HEAD

    class CausalMHA(nn.Module):
        """Hand-rolled causal multi-head attention (weight-layout compatible
        with nn.MultiheadAttention: qkv = stacked Q/K/V in-proj). Written
        with explicit matmuls so the dynamo ONNX exporter keeps batch/seq
        symbolic (nn.MultiheadAttention decomposition bakes batch=1)."""

        def __init__(self):
            super().__init__()
            self.qkv = nn.Linear(D_MODEL, 3 * D_MODEL)
            self.out = nn.Linear(D_MODEL, D_MODEL)

        def forward(self, x):
            b, t, _ = x.shape
            q, k, v = self.qkv(x).view(b, t, 3, N_HEAD, HEAD_DIM).unbind(2)
            q = q.transpose(1, 2)
            k = k.transpose(1, 2)
            v = v.transpose(1, 2)
            att = (q @ k.transpose(-2, -1)) / math.sqrt(HEAD_DIM)
            mask = torch.triu(torch.ones(t, t, dtype=torch.bool, device=x.device), 1)
            att = att.masked_fill(mask, float("-inf"))
            y = (torch.softmax(att, dim=-1) @ v).transpose(1, 2).reshape(b, t, D_MODEL)
            return self.out(y)

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.ln1 = nn.LayerNorm(D_MODEL)
            self.attn = CausalMHA()
            self.ln2 = nn.LayerNorm(D_MODEL)
            self.ff = nn.Sequential(nn.Linear(D_MODEL, D_FF), nn.GELU(),
                                    nn.Linear(D_FF, D_MODEL))

        def forward(self, x):
            x = x + self.attn(self.ln1(x))
            return x + self.ff(self.ln2(x))

    class TinyLM(nn.Module):
        def __init__(self):
            super().__init__()
            self.tok = nn.Embedding(VOCAB, D_MODEL)
            self.pos = nn.Embedding(CTX, D_MODEL)
            self.slot = nn.Embedding(7, D_MODEL)  # 0: count head, 1..6: note slots
            self.blocks = nn.ModuleList([Block() for _ in range(N_LAYER)])
            self.ln = nn.LayerNorm(D_MODEL)
            self.head = nn.Linear(D_MODEL, VOCAB, bias=False)

        def forward(self, ids):
            b, t = ids.shape
            # Slot pattern depends on t only ([t] vector, broadcast over batch
            # like the pos embedding) so the exporter keeps batch symbolic.
            ar = torch.arange(t, device=ids.device)
            slot1d = torch.where(ar == 0, 0, ((ar + 5) % 6) + 1)
            x = (self.tok(ids) + self.pos.weight[:t].unsqueeze(0)
                 + self.slot(slot1d).unsqueeze(0))
            for blk in self.blocks:
                x = blk(x)
            return self.head(self.ln(x))

    model = TinyLM()
    n = sum(p.numel() for p in model.parameters())
    assert n <= 2_000_000, "R3 param budget exceeded"
    return model


def param_count(model) -> int:
    return sum(p.numel() for p in model.parameters())
