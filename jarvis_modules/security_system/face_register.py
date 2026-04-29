"""
═══════════════════════════════════════════════════════════════
  Cadastro Facial v2.1 — COM Preview da Webcam
═══════════════════════════════════════════════════════════════

Cadastro com janela da webcam visível mostrando progresso.
Roda em background thread para não bloquear o agente.

Backends:
  • face_recognition (dlib) — 128-dim embeddings
  • OpenCV Haar+LBPH — fallback sem deps extras
"""

import os
import pickle
import time
import logging
import threading

logger = logging.getLogger(__name__)

# ── Diretórios ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SECURITY_DIR = os.path.join(BASE_DIR, "data", "security")
FACES_DIR = os.path.join(SECURITY_DIR, "faces")
ENCODINGS_FILE = os.path.join(SECURITY_DIR, "face_encodings.pkl")
LBPH_MODEL_FILE = os.path.join(SECURITY_DIR, "lbph_model.yml")
LABELS_FILE = os.path.join(SECURITY_DIR, "labels.pkl")

os.makedirs(FACES_DIR, exist_ok=True)

# ── Detectar backends ────────────────────────────────────────
_FACE_REC_OK = False
_OPENCV_OK = False

try:
    import face_recognition
    _FACE_REC_OK = True
except ImportError:
    pass

try:
    import cv2
    _OPENCV_OK = True
except ImportError:
    pass

# ── Estado global do cadastro (para não bloquear) ────────────
_cadastro_em_andamento = False
_cadastro_resultado = ""


class FaceRegister:
    """Gerenciador de cadastro facial com preview da webcam."""

    def __init__(self):
        self._encodings_db = {}
        self._backend = "none"
        self._lock = threading.Lock()
        self._load_db()

    def _load_db(self):
        if os.path.exists(ENCODINGS_FILE):
            try:
                with open(ENCODINGS_FILE, "rb") as f:
                    self._encodings_db = pickle.load(f)
                self._backend = "face_recognition" if _FACE_REC_OK else "opencv_lbph"
                logger.info(
                    f"[FaceRegister] {len(self._encodings_db)} usuario(s) | "
                    f"Backend: {self._backend}"
                )
            except Exception as e:
                logger.error(f"[FaceRegister] Erro ao carregar DB: {e}")
        elif _OPENCV_OK and os.path.exists(LBPH_MODEL_FILE):
            self._backend = "opencv_lbph"
        else:
            self._backend = "face_recognition" if _FACE_REC_OK else "opencv_lbph"

    def _save_db(self):
        with self._lock:
            try:
                os.makedirs(os.path.dirname(ENCODINGS_FILE), exist_ok=True)
                with open(ENCODINGS_FILE, "wb") as f:
                    pickle.dump(self._encodings_db, f)
                logger.info("[FaceRegister] DB salvo")
            except Exception as e:
                logger.error(f"[FaceRegister] Erro ao salvar DB: {e}")

    # ═══════════════════════════════════════════════════════════
    #  Cadastro com Webcam (ABRE JANELA)
    # ═══════════════════════════════════════════════════════════

    def cadastrar_via_webcam(self, nome: str, num_amostras: int = 10) -> str:
        """
        Inicia cadastro em background com janela da webcam visível.
        Retorna imediatamente para não bloquear o agente.
        """
        global _cadastro_em_andamento

        if not _OPENCV_OK:
            return "OpenCV nao instalado."

        if not nome or not nome.strip():
            return "Nome do usuario e obrigatorio."

        if _cadastro_em_andamento:
            return "Cadastro ja em andamento. Aguarde a janela da webcam."

        nome = nome.strip()
        _cadastro_em_andamento = True

        # Iniciar em thread separada (NÃO bloqueia o agente)
        t = threading.Thread(
            target=self._cadastro_com_preview,
            args=(nome, num_amostras),
            daemon=True,
        )
        t.start()

        return (
            f"Cadastro de '{nome}' INICIADO!\n\n"
            f"Uma janela da webcam ira abrir.\n"
            f"Posicione seu rosto na camera.\n"
            f"O sistema capturara {num_amostras} amostras automaticamente.\n"
            f"Pressione Q para cancelar."
        )

    def _cadastro_com_preview(self, nome: str, num_amostras: int):
        """Processo de cadastro com janela cv2.imshow visível."""
        global _cadastro_em_andamento, _cadastro_resultado
        import cv2
        from .camera_utils import abrir_webcam

        cap = abrir_webcam(640, 480)
        if cap is None:
            _cadastro_em_andamento = False
            _cadastro_resultado = "Webcam nao disponivel."
            logger.error("[FaceRegister] Webcam nao disponivel")
            return

        # Criar janela
        window_name = "JARVIS - Cadastro Facial"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
        try:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
        except Exception:
            pass

        user_dir = os.path.join(FACES_DIR, nome)
        os.makedirs(user_dir, exist_ok=True)

        encodings = []
        captured = 0
        frame_count = 0
        last_capture_time = 0.0

        logger.info(f"[FaceRegister] Cadastro com preview: '{nome}'")

        while captured < num_amostras:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            frame_count += 1
            now = time.time()

            # ── HUD ──────────────────────────────────────────
            h, w = frame.shape[:2]

            # Fundo semi-transparente no topo
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

            cv2.putText(
                frame, f"JARVIS - Cadastro: {nome}",
                (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2,
            )
            cv2.putText(
                frame, f"Capturado: {captured}/{num_amostras}",
                (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
            )

            # Barra de progresso
            pct = captured / num_amostras
            bar_w = int((w - 30) * pct)
            cv2.rectangle(frame, (15, 65), (15 + bar_w, 75), (0, 255, 0), -1)
            cv2.rectangle(frame, (15, 65), (w - 15, 75), (100, 100, 100), 1)

            # Instruções
            cv2.putText(
                frame, "Olhe para a camera. Q para cancelar.",
                (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1,
            )

            # ── Captura a cada 0.5s ──────────────────────────
            should_capture = (now - last_capture_time > 0.5) and (frame_count > 15)

            if should_capture:
                if _FACE_REC_OK:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    locations = face_recognition.face_locations(rgb, model="hog")
                    encs = face_recognition.face_encodings(rgb, locations)

                    if encs and len(locations) == 1:
                        encodings.append(encs[0])
                        captured += 1
                        last_capture_time = now

                        # Salvar foto
                        photo_path = os.path.join(user_dir, f"{nome}_{captured:03d}.jpg")
                        cv2.imwrite(photo_path, frame)

                        # Flash verde
                        for top, right, bottom, left in locations:
                            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 3)
                            cv2.putText(
                                frame, f"CAPTURADO!",
                                (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
                            )

                        logger.info(f"[FaceRegister] Captura {captured}/{num_amostras}")
                    else:
                        # Desenhar retângulo vermelho se rosto não detectado
                        cv2.putText(
                            frame, "Posicione seu rosto...",
                            (15, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1,
                        )
                else:
                    # Fallback Haar
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    cascade = cv2.CascadeClassifier(
                        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                    )
                    faces = cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))

                    if len(faces) == 1:
                        x, y, fw, fh = faces[0]
                        face_roi = cv2.resize(gray[y:y+fh, x:x+fw], (200, 200))
                        encodings.append(face_roi)
                        captured += 1
                        last_capture_time = now

                        photo_path = os.path.join(user_dir, f"{nome}_{captured:03d}.jpg")
                        cv2.imwrite(photo_path, frame)

                        cv2.rectangle(frame, (x, y), (x+fw, y+fh), (0, 255, 0), 3)
                        logger.info(f"[FaceRegister] Haar captura {captured}/{num_amostras}")

            # ── Mostrar janela ───────────────────────────────
            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("[FaceRegister] Cancelado pelo usuario")
                break

        # ── Finalizar ────────────────────────────────────────
        cap.release()
        cv2.destroyAllWindows()

        if encodings:
            with self._lock:
                if nome not in self._encodings_db:
                    self._encodings_db[nome] = []
                self._encodings_db[nome].extend(encodings)
            self._save_db()
            _cadastro_resultado = (
                f"Cadastro concluido! Usuario: {nome} | "
                f"Amostras: {len(encodings)}"
            )
            logger.info(f"[FaceRegister] Cadastro concluido: {nome} ({len(encodings)} amostras)")
        else:
            _cadastro_resultado = "Nenhum rosto capturado."
            logger.warning("[FaceRegister] Nenhum rosto capturado")

        _cadastro_em_andamento = False

    # ═══════════════════════════════════════════════════════════
    #  Cadastro via Imagem
    # ═══════════════════════════════════════════════════════════

    def cadastrar_via_imagem(self, nome: str, caminho_imagem: str) -> str:
        if not os.path.exists(caminho_imagem):
            return f"Arquivo nao encontrado: {caminho_imagem}"

        if _FACE_REC_OK:
            import face_recognition as fr
            image = fr.load_image_file(caminho_imagem)
            encs = fr.face_encodings(image)
            if not encs:
                return f"Nenhum rosto encontrado em: {caminho_imagem}"
            with self._lock:
                if nome not in self._encodings_db:
                    self._encodings_db[nome] = []
                self._encodings_db[nome].extend(encs)
            self._save_db()
            return f"{len(encs)} rosto(s) de '{nome}' registrado(s) via imagem."

        if _OPENCV_OK:
            import cv2
            import numpy as np
            img = cv2.imread(caminho_imagem)
            if img is None:
                return f"Nao foi possivel ler: {caminho_imagem}"
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))
            if len(faces) == 0:
                return f"Nenhum rosto detectado em: {caminho_imagem}"
            x, y, w, h = faces[0]
            face_roi = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
            with self._lock:
                if nome not in self._encodings_db:
                    self._encodings_db[nome] = []
                self._encodings_db[nome].append(face_roi)
            self._save_db()
            return f"Rosto de '{nome}' registrado via imagem (Haar)."

        return "Nenhum backend disponivel."

    # ═══════════════════════════════════════════════════════════
    #  Gerenciamento
    # ═══════════════════════════════════════════════════════════

    def listar_usuarios(self) -> str:
        if not self._encodings_db:
            if os.path.exists(LABELS_FILE):
                with open(LABELS_FILE, "rb") as f:
                    labels = pickle.load(f)
                if labels:
                    linhas = ["Usuarios cadastrados (LBPH):\n"]
                    for name, lid in labels.items():
                        linhas.append(f"  {name} (label={lid})")
                    return "\n".join(linhas)
            return "Nenhum usuario cadastrado."

        linhas = ["Usuarios cadastrados:\n"]
        for name, encs in self._encodings_db.items():
            linhas.append(f"  {name} - {len(encs)} amostras")
        linhas.append(f"\n  Backend: {self._backend}")
        return "\n".join(linhas)

    def remover_usuario(self, nome: str) -> str:
        with self._lock:
            if nome in self._encodings_db:
                del self._encodings_db[nome]
                self._save_db()
                user_dir = os.path.join(FACES_DIR, nome)
                if os.path.exists(user_dir):
                    import shutil
                    shutil.rmtree(user_dir, ignore_errors=True)
                return f"Usuario '{nome}' removido."
        return f"Usuario '{nome}' nao encontrado."

    def get_all_encodings(self) -> tuple:
        encodings, names = [], []
        for name, encs in self._encodings_db.items():
            for enc in encs:
                encodings.append(enc)
                names.append(name)
        return encodings, names

    def tem_cadastro(self) -> bool:
        return bool(self._encodings_db) or os.path.exists(LBPH_MODEL_FILE)

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def num_usuarios(self) -> int:
        return len(self._encodings_db)
