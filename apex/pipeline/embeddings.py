"""OSNet appearance embedder with ResNet-18 fallback.

Priority:
  1. torchreid OSNet-x0_25 (best Re-ID accuracy)
  2. torchvision ResNet-18 features (decent fallback)
  3. OpenCV colour histogram (stub fallback, no torch)
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Try torchreid ─────────────────────────────────────────────────────────────
try:
    import torchreid
    _TORCHREID_AVAILABLE = True
except ImportError:
    _TORCHREID_AVAILABLE = False

# ── Try torch / torchvision ───────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torchvision.models as tv_models
    import torchvision.transforms as T
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

_EMBED_DIM = 128   # output dimensionality (all backends normalised to this)


class AppearanceEmbedder:
    """Extract 128-dim L2-normalised appearance embeddings from person crops.

    Backends (selected automatically):
      - OSNet-x0_25 via torchreid  → best Re-ID quality
      - ResNet-18 global avg pool   → good quality, no extra dependency
      - HSV colour histogram         → lightweight stub (no torch)
    """

    def __init__(self, model_name: str = "osnet_x0_25", device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self._backend = "histogram"
        self._model = None
        self._transform = None
        self._init_backend()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_backend(self) -> None:
        if _TORCHREID_AVAILABLE and _TORCH_AVAILABLE:
            self._init_osnet()
        elif _TORCH_AVAILABLE:
            self._init_resnet()
        else:
            self._backend = "histogram"
            logger.warning(
                "AppearanceEmbedder: no torch — using HSV histogram (128-dim)."
            )

    def _init_osnet(self) -> None:
        try:
            self._model = torchreid.models.build_model(
                name=self.model_name,
                num_classes=1000,
                pretrained=True,
            )
            self._model.eval()
            if self.device == "cuda" and _TORCH_AVAILABLE and torch.cuda.is_available():
                self._model = self._model.cuda()
            self._transform = T.Compose([
                T.ToPILImage(),
                T.Resize((256, 128)),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])
            self._backend = "osnet"
            logger.info("AppearanceEmbedder: using OSNet-x0_25 (torchreid)")
        except Exception as exc:
            logger.warning("OSNet init failed (%s) — falling back to ResNet-18", exc)
            self._init_resnet()

    def _init_resnet(self) -> None:
        try:
            base = tv_models.resnet18(weights=tv_models.ResNet18_Weights.IMAGENET1K_V1)
            # Remove final classifier; use avgpool output (512-dim → projected to 128)
            self._model = nn.Sequential(
                *list(base.children())[:-1],
                nn.Flatten(),
                nn.Linear(512, _EMBED_DIM),
            )
            self._model.eval()
            if self.device == "cuda" and torch.cuda.is_available():
                self._model = self._model.cuda()
            self._transform = T.Compose([
                T.ToPILImage(),
                T.Resize((256, 128)),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])
            self._backend = "resnet18"
            logger.info("AppearanceEmbedder: using ResNet-18 fallback")
        except Exception as exc:
            logger.warning("ResNet-18 init failed (%s) — using histogram", exc)
            self._backend = "histogram"

    # ── Embedding extraction ──────────────────────────────────────────────────

    def extract(self, frame: np.ndarray, bbox: List[float]) -> np.ndarray:
        """Crop person from frame using bbox and return 128-dim embedding.

        Args:
            frame: Full BGR frame (H×W×3).
            bbox:  [x1, y1, x2, y2] pixel coordinates.

        Returns:
            L2-normalised 128-dim float32 numpy array.
        """
        crop = self._crop(frame, bbox)
        if crop is None or crop.size == 0:
            return np.zeros(_EMBED_DIM, dtype=np.float32)

        if self._backend in ("osnet", "resnet18"):
            return self._torch_embed(crop)
        return self._histogram_embed(crop)

    def _crop(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        if frame is None or len(frame.shape) != 3:
            return None
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = (int(max(0, v)) for v in bbox)
        x2, y2 = min(x2, w), min(y2, h)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    def _torch_embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        try:
            import torch
            # Convert BGR → RGB for torchvision
            crop_rgb = crop_bgr[:, :, ::-1].copy()
            tensor = self._transform(crop_rgb).unsqueeze(0)
            if self.device == "cuda" and torch.cuda.is_available():
                tensor = tensor.cuda()
            with torch.no_grad():
                feat = self._model(tensor)
            vec = feat.cpu().numpy().flatten()
            # Resize/project to _EMBED_DIM if needed
            if vec.shape[0] != _EMBED_DIM:
                # Linear interpolation resize
                indices = np.linspace(0, vec.shape[0] - 1, _EMBED_DIM)
                vec = np.interp(indices, np.arange(vec.shape[0]), vec)
            return self._l2_norm(vec.astype(np.float32))
        except Exception as exc:
            logger.debug("Torch embed error: %s", exc)
            return np.zeros(_EMBED_DIM, dtype=np.float32)

    def _histogram_embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        """HSV colour histogram (3×16 bins = 48 dims) + LBP texture (80 dims) = 128."""
        if not _CV2_AVAILABLE:
            return np.zeros(_EMBED_DIM, dtype=np.float32)

        import cv2  # noqa: PLC0415

        try:
            resized = cv2.resize(crop_bgr, (64, 128))
            hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)

            # HSV histogram: H(16) + S(16) + V(16) = 48 dims
            h_hist = cv2.calcHist([hsv], [0], None, [16], [0, 180]).flatten()
            s_hist = cv2.calcHist([hsv], [1], None, [16], [0, 256]).flatten()
            v_hist = cv2.calcHist([hsv], [2], None, [16], [0, 256]).flatten()
            color_feat = np.concatenate([h_hist, s_hist, v_hist])  # 48-dim

            # Spatial grid colour (4×4 grid, 5 bins per channel) = 80 dims
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            rows, cols = gray.shape
            cell_h, cell_w = rows // 4, cols // 4
            texture_feat = []
            for r in range(4):
                for c in range(4):
                    cell = gray[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
                    hist = cv2.calcHist([cell], [0], None, [5], [0, 256]).flatten()
                    texture_feat.extend(hist.tolist())
            texture_feat = np.array(texture_feat[:80], dtype=np.float32)  # 80-dim

            feat = np.concatenate([color_feat, texture_feat]).astype(np.float32)
            # Pad or trim to _EMBED_DIM
            if feat.shape[0] < _EMBED_DIM:
                feat = np.pad(feat, (0, _EMBED_DIM - feat.shape[0]))
            else:
                feat = feat[:_EMBED_DIM]

            return self._l2_norm(feat)
        except Exception as exc:
            logger.debug("Histogram embed error: %s", exc)
            return np.zeros(_EMBED_DIM, dtype=np.float32)

    # ── Similarity ────────────────────────────────────────────────────────────

    @staticmethod
    def similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity in [−1, 1], clipped to [0, 1] for use as confidence."""
        n1 = np.linalg.norm(emb1)
        n2 = np.linalg.norm(emb2)
        if n1 < 1e-8 or n2 < 1e-8:
            return 0.0
        cos = float(np.dot(emb1, emb2) / (n1 * n2))
        return float(np.clip(cos, 0.0, 1.0))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _l2_norm(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm < 1e-8:
            return vec
        return vec / norm

    @property
    def backend(self) -> str:
        return self._backend
