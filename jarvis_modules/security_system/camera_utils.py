"""
═══════════════════════════════════════════════════════════════
  Utilitário de Câmera — Detecta webcam real no Windows
═══════════════════════════════════════════════════════════════

Problema: Câmeras virtuais (Animaze, OBS Virtual Cam, etc.)
ocupam index 0. Webcam real pode dar tela preta sem warmup.

Solução: Testa câmeras 0-4 com warmup e encontra a que
produz frames reais (não pretos, não estáticos).
"""

import logging
import time

logger = logging.getLogger(__name__)

_cached_camera_index = None


def encontrar_webcam_real(max_index: int = 5) -> int:
    """
    Encontra o index da webcam real (não virtual, não preta).

    Testa câmeras com warmup robusto:
      1. Abre câmera
      2. Descarta 30 frames de warmup (evita tela preta)
      3. Captura 2 frames e compara
      4. Se diferentes E não pretos = webcam real

    Returns:
        Index da câmera real, ou 0 como fallback.
    """
    global _cached_camera_index

    if _cached_camera_index is not None:
        return _cached_camera_index

    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0

    logger.info("[Camera] Procurando webcam real...")

    best_index = 0
    best_brightness = 0.0

    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Warmup robusto: descartar frames iniciais pretos
        for _ in range(30):
            cap.read()

        # Esperar um pouco para estabilizar
        time.sleep(0.5)

        # Ler frames de teste
        ret1, frame1 = cap.read()
        if not ret1 or frame1 is None:
            cap.release()
            continue

        time.sleep(0.2)
        ret2, frame2 = cap.read()
        if not ret2 or frame2 is None:
            cap.release()
            continue

        # Métricas
        brightness = float(np.mean(frame1))
        diff = float(np.mean(np.abs(frame1.astype(float) - frame2.astype(float))))
        h, w = frame1.shape[:2]
        is_black = brightness < 10.0
        is_static = diff < 0.5

        cap.release()

        status = []
        if is_black:
            status.append("PRETA")
        if is_static:
            status.append("ESTATICA")
        if not is_black and not is_static:
            status.append("REAL")

        logger.info(
            f"[Camera] Index {idx}: {w}x{h} | "
            f"Brilho: {brightness:.1f} | Variacao: {diff:.2f} | "
            f"{'/'.join(status)}"
        )

        # Melhor câmera = não preta + não estática + mais brilhante
        if not is_black and not is_static:
            if brightness > best_brightness:
                best_brightness = brightness
                best_index = idx

    if best_brightness > 0:
        _cached_camera_index = best_index
        logger.info(f"[Camera] ✅ Webcam real: index {best_index} (brilho: {best_brightness:.1f})")
        return best_index

    # Fallback: pegar a mais brilhante mesmo
    logger.warning(f"[Camera] ⚠️ Usando index {best_index} como fallback")
    _cached_camera_index = best_index
    return best_index


def abrir_webcam(width: int = 640, height: int = 480):
    """
    Abre a webcam real com warmup para evitar tela preta.

    Returns:
        cv2.VideoCapture configurado ou None se falhar.
    """
    import cv2

    idx = encontrar_webcam_real()
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)

    if not cap.isOpened():
        logger.error(f"[Camera] Falha ao abrir webcam index {idx}")
        return None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, 30)

    # Warmup: descartar frames pretos iniciais
    logger.info(f"[Camera] Warmup da webcam index {idx}...")
    for i in range(40):
        ret, _ = cap.read()
        if not ret:
            time.sleep(0.05)
    time.sleep(0.3)

    real_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    real_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"[Camera] Webcam pronta: index {idx} | {real_w}x{real_h}")

    return cap


def resetar_cache():
    """Reseta cache para forçar nova detecção."""
    global _cached_camera_index
    _cached_camera_index = None
