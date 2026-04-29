"""
═══════════════════════════════════════════════════════════════
  Reconhecimento Facial v2.0 — Multi-Backend + Detection-Only
═══════════════════════════════════════════════════════════════

Backends (em ordem de prioridade):
  1. face_recognition (dlib) — 128-dim embeddings, alta precisão
  2. OpenCV LBPH — modelo treinado localmente
  3. Detection-Only — Haar cascade (sem reconhecimento,
     todos os rostos são INTRUSO)

Sempre inicializa com pelo menos detecção facial ativa.
"""

import os
import pickle
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SECURITY_DIR = os.path.join(BASE_DIR, "data", "security")
LBPH_MODEL_FILE = os.path.join(SECURITY_DIR, "lbph_model.yml")
LABELS_FILE = os.path.join(SECURITY_DIR, "labels.pkl")

_FACE_REC_OK = False
try:
    import face_recognition as _fr
    _FACE_REC_OK = True
except ImportError:
    pass


class FaceRecognizer:
    """Reconhecedor facial multi-backend com fallback de detecção."""

    INTRUSO = "INTRUSO"
    AUTORIZADO = "AUTORIZADO"

    def __init__(self, tolerance: float = 0.55):
        self.tolerance = tolerance
        self._known_encodings = []
        self._known_names = []
        self._backend = "none"

        # OpenCV LBPH
        self._lbph_recognizer = None
        self._lbph_labels = {}
        self._lbph_id_to_name = {}
        self._lbph_threshold = 80

        # Haar cascade (sempre disponível como fallback)
        self._face_cascade = None

    def start(self, encodings: list = None, names: list = None) -> bool:
        """
        Inicializa reconhecedor.
        SEMPRE retorna True se OpenCV estiver disponível
        (pelo menos detecção funciona).
        """
        import cv2

        # Inicializar Haar cascade (sempre necessário para detecção)
        try:
            self._face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        except Exception as e:
            logger.error(f"[FaceRecognizer] Erro ao carregar Haar cascade: {e}")

        # 1. Tentar face_recognition (melhor opção)
        if _FACE_REC_OK and encodings and names:
            self._known_encodings = encodings
            self._known_names = names
            self._backend = "face_recognition"
            logger.info(
                f"[FaceRecognizer] Backend: face_recognition | "
                f"Tolerance: {self.tolerance} | "
                f"{len(set(names))} usuário(s)"
            )
            return True

        # 2. Tentar LBPH (fallback)
        if os.path.exists(LBPH_MODEL_FILE):
            try:
                self._lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()
                self._lbph_recognizer.read(LBPH_MODEL_FILE)

                if os.path.exists(LABELS_FILE):
                    with open(LABELS_FILE, "rb") as f:
                        self._lbph_labels = pickle.load(f)
                    self._lbph_id_to_name = {v: k for k, v in self._lbph_labels.items()}

                self._backend = "opencv_lbph"
                logger.info(
                    f"[FaceRecognizer] Backend: OpenCV LBPH | "
                    f"{len(self._lbph_labels)} usuário(s)"
                )
                return True
            except Exception as e:
                logger.warning(f"[FaceRecognizer] LBPH falhou: {e}")

        # 3. Detection-only (Haar cascade apenas)
        if self._face_cascade is not None:
            self._backend = "detection_only"
            logger.warning(
                "[FaceRecognizer] Backend: detection_only (Haar cascade) — "
                "todos os rostos serão marcados como INTRUSO. "
                "Cadastre rostos para reconhecimento."
            )
            return True

        logger.error("[FaceRecognizer] Nenhum backend disponível")
        return False

    def reconhecer(self, frame_bgr, frame_rgb=None) -> list:
        """
        Reconhece/detecta rostos no frame.

        Returns:
            Lista de dicts com nome, autorizado, localizacao, confianca.
        """
        if self._backend == "face_recognition":
            return self._reconhecer_fr(frame_bgr, frame_rgb)
        elif self._backend == "opencv_lbph":
            return self._reconhecer_lbph(frame_bgr)
        elif self._backend == "detection_only":
            return self._detectar_apenas(frame_bgr)
        return []

    def _reconhecer_fr(self, frame_bgr, frame_rgb=None) -> list:
        """Reconhecimento via face_recognition (128-dim embeddings)."""
        import cv2

        if frame_rgb is None:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        face_locations = _fr.face_locations(frame_rgb, model="hog")
        if not face_locations:
            return []

        face_encodings = _fr.face_encodings(frame_rgb, face_locations)
        results = []

        for encoding, location in zip(face_encodings, face_locations):
            nome = self.INTRUSO
            confianca = 0.0
            autorizado = False

            if self._known_encodings:
                distances = _fr.face_distance(self._known_encodings, encoding)
                matches = _fr.compare_faces(
                    self._known_encodings, encoding, tolerance=self.tolerance
                )

                if True in matches:
                    best_idx = distances.argmin()
                    if matches[best_idx]:
                        nome = self._known_names[best_idx]
                        confianca = 1.0 - float(distances[best_idx])
                        autorizado = True
                else:
                    confianca = 1.0 - float(distances.min()) if len(distances) > 0 else 0.0

            results.append({
                "nome": nome,
                "autorizado": autorizado,
                "localizacao": location,
                "confianca": confianca,
            })

        return results

    def _reconhecer_lbph(self, frame_bgr) -> list:
        """Reconhecimento via OpenCV LBPH."""
        import cv2

        if self._face_cascade is None or self._lbph_recognizer is None:
            return self._detectar_apenas(frame_bgr)

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))

        results = []
        for (x, y, w, h) in faces:
            face_roi = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
            label_id, confidence = self._lbph_recognizer.predict(face_roi)

            nome = self.INTRUSO
            autorizado = False

            if confidence < self._lbph_threshold:
                nome = self._lbph_id_to_name.get(label_id, self.INTRUSO)
                autorizado = nome != self.INTRUSO

            location = (y, x + w, y + h, x)
            results.append({
                "nome": nome,
                "autorizado": autorizado,
                "localizacao": location,
                "confianca": 1.0 - (confidence / 200.0) if confidence < 200 else 0.0,
            })

        return results

    def _detectar_apenas(self, frame_bgr) -> list:
        """Detection-only: detecta rostos mas não reconhece."""
        import cv2

        if self._face_cascade is None:
            return []

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))

        results = []
        for (x, y, w, h) in faces:
            location = (y, x + w, y + h, x)  # (top, right, bottom, left)
            results.append({
                "nome": self.INTRUSO,
                "autorizado": False,
                "localizacao": location,
                "confianca": 0.0,
            })

        return results

    @property
    def backend(self) -> str:
        return self._backend

    def stop(self):
        self._known_encodings = []
        self._known_names = []
        self._lbph_recognizer = None
        logger.info("[FaceRecognizer] Encerrado")
