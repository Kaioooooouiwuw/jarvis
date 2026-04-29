"""
═══════════════════════════════════════════════════════════════
  JARVIS SECURITY CAMERA ENGINE v1.0
  Segurança Inteligente: Câmera + Reconhecimento Facial + YOLO
═══════════════════════════════════════════════════════════════

  Sistema de segurança em tempo real:
    📷 Webcam          → Monitoramento contínuo
    🧑 YOLO            → Detecta presença de pessoas
    👤 Face Recognition → Identifica AUTORIZADO vs INTRUSO
    🚨 Alarme          → alarme.mp3 em loop + captura de foto

  Fluxo:
    1. Pessoa detectada no frame (YOLO/HOG)
    2. Verificação facial de todos os rostos visíveis
    3. Se rosto == cadastrado → marca como AUTORIZADO
    4. Se rosto != cadastrado → acumula frames consecutivos
    5. Após N frames de intruso confirmado → ALERTA!

  Segurança:
    • 10 frames consecutivos antes de disparar alerta
    • Cooldown de 15s entre alertas
    • Código secreto de voz para desativar
    • HUD overlay com status em tempo real

  Ativação por voz:
    "Jarvis, ative o modo alerta de segurança"
    "Jarvis, desative o modo alerta de segurança"
    "Jarvis, código alfa desativar"
"""

import os
import time
import threading
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Estado Global
# ═══════════════════════════════════════════════════════════════

_seguranca_ativa = False
_thread_seguranca = None

# Sub-sistemas
_face_register = None
_alert_system = None

# Configurações
_INTRUSO_FRAMES_THRESHOLD = 10   # Frames consecutivos para confirmar intruso
_PROCESS_EVERY_N_FRAMES = 3      # Processar face a cada N frames (performance)
_ALERT_COOLDOWN = 15.0            # Segundos entre alertas


# ═══════════════════════════════════════════════════════════════
#  Verificação de Dependências
# ═══════════════════════════════════════════════════════════════

def _verificar_deps() -> dict:
    """Verifica dependências do sistema de segurança."""
    status = {}

    try:
        import cv2
        status["opencv"] = f"✅ OpenCV {cv2.__version__}"
    except ImportError:
        status["opencv"] = "❌ opencv-python"

    try:
        import face_recognition
        status["face_recognition"] = "✅ face_recognition (dlib)"
    except ImportError:
        status["face_recognition"] = "⚠️ face_recognition (usando fallback OpenCV)"

    try:
        from ultralytics import YOLO
        status["yolo"] = "✅ YOLOv8 (ultralytics)"
    except ImportError:
        status["yolo"] = "⚠️ ultralytics (usando fallback HOG)"

    try:
        import pygame
        status["pygame"] = f"✅ pygame {pygame.__version__}"
    except ImportError:
        status["pygame"] = "❌ pygame (alarme desabilitado)"

    return status


def _deps_minimos_ok() -> bool:
    """Verifica deps mínimas (OpenCV é obrigatório)."""
    try:
        import cv2
        return True
    except ImportError:
        return False


# ═══════════════════════════════════════════════════════════════
#  HUD — Interface Visual
# ═══════════════════════════════════════════════════════════════

def _draw_security_hud(frame, pessoas, rostos, intruso_count, fps,
                        alarme_ativo, total_alertas):
    """Desenha HUD de segurança sobre o frame."""
    import cv2

    h, w = frame.shape[:2]

    # ── Barra superior ───────────────────────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # Título
    cv2.putText(
        frame, "JARVIS SECURITY",
        (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 100, 255), 2,
    )

    # Status
    if alarme_ativo:
        # Piscar vermelho
        if int(time.time() * 3) % 2:
            cv2.putText(
                frame, "ALERTA ATIVO",
                (w - 250, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
            )
        # Ícone de alerta
        cv2.circle(frame, (w - 270, 22), 8, (0, 0, 255), -1)
    else:
        cv2.putText(
            frame, "MONITORANDO",
            (w - 230, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
        )
        cv2.circle(frame, (w - 250, 22), 8, (0, 255, 0), -1)

    # Info
    cv2.putText(
        frame, f"Pessoas: {len(pessoas)} | Rostos: {len(rostos)} | Alertas: {total_alertas}",
        (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
    )

    # FPS
    cv2.putText(
        frame, f"FPS: {fps:.0f}",
        (w - 120, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1,
    )

    # Barra de intruso (se acumulando frames)
    if intruso_count > 0 and intruso_count < _INTRUSO_FRAMES_THRESHOLD:
        pct = intruso_count / _INTRUSO_FRAMES_THRESHOLD
        bar_w = int(250 * pct)
        cv2.putText(
            frame, f"Verificando intruso: {intruso_count}/{_INTRUSO_FRAMES_THRESHOLD}",
            (15, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1,
        )
        cv2.rectangle(frame, (260, 68), (260 + bar_w, 82), (0, 200, 255), -1)
        cv2.rectangle(frame, (260, 68), (510, 82), (100, 100, 100), 1)

    # ── Bounding boxes de pessoas ────────────────────────────
    for pessoa in pessoas:
        x1, y1, x2, y2 = pessoa["bbox"]
        conf = pessoa["confianca"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 1)
        cv2.putText(
            frame, f"Pessoa {conf:.0%}",
            (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 200, 0), 1,
        )

    # ── Labels de rostos reconhecidos ────────────────────────
    for rosto in rostos:
        top, right, bottom, left = rosto["localizacao"]
        nome = rosto["nome"]
        autorizado = rosto["autorizado"]
        conf = rosto["confianca"]

        if autorizado:
            cor = (0, 255, 0)      # Verde
            label = f"{nome.upper()} (AUTORIZADO)"
        else:
            cor = (0, 0, 255)      # Vermelho
            label = f"INTRUSO"

        # Borda do rosto
        cv2.rectangle(frame, (left, top), (right, bottom), cor, 2)

        # Label com fundo
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(
            frame, (left, top - 25), (left + label_size[0] + 10, top), cor, -1,
        )
        cv2.putText(
            frame, label,
            (left + 5, top - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
        )

    # ── Rodapé ───────────────────────────────────────────────
    cv2.putText(
        frame, "Q=Sair | ESC=Parar Alarme",
        (w - 280, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1,
    )


# ═══════════════════════════════════════════════════════════════
#  Loop Principal de Segurança
# ═══════════════════════════════════════════════════════════════

def _loop_seguranca():
    """Loop principal do sistema de segurança. Roda em thread daemon."""
    global _seguranca_ativa, _face_register, _alert_system

    # ── Imports ──────────────────────────────────────────────
    try:
        import cv2
    except ImportError:
        logger.error("[Segurança] OpenCV não disponível")
        _seguranca_ativa = False
        return

    from .security_system.face_register import FaceRegister
    from .security_system.face_recognizer import FaceRecognizer
    from .security_system.person_detector import PersonDetector
    from .security_system.alert_system import AlertSystem

    # ── Inicializar sub-sistemas ─────────────────────────────
    _face_register = FaceRegister()
    recognizer = FaceRecognizer(tolerance=0.55)
    detector = PersonDetector(confidence=0.5, use_yolo=True)
    _alert_system = AlertSystem(cooldown=_ALERT_COOLDOWN, alarm_volume=1.0)

    # Carregar rostos cadastrados
    if _face_register.tem_cadastro():
        encodings, names = _face_register.get_all_encodings()
        if not recognizer.start(encodings, names):
            logger.warning("[Segurança] Reconhecedor facial iniciado sem dados")
        else:
            logger.info(
                f"[Segurança] {len(set(names))} usuário(s) autorizado(s) carregado(s)"
            )
    else:
        recognizer.start()
        logger.warning(
            "[Segurança] ⚠️ Nenhum rosto cadastrado! "
            "Todas as pessoas serão marcadas como INTRUSO. "
            "Use cadastrar_rosto primeiro."
        )

    # Inicializar detector de pessoas
    if not detector.start():
        logger.warning(
            "[Segurança] Detector de pessoas indisponível. "
            "Usando apenas reconhecimento facial."
        )

    # Câmera — auto-detecta webcam real (ignora virtual como Animaze)
    from .security_system.camera_utils import abrir_webcam
    cap = abrir_webcam(640, 480)
    if cap is None:
        logger.error("[Segurança] Webcam não disponível")
        _seguranca_ativa = False
        return

    logger.info("═══════════════════════════════════════════")
    logger.info("  🔴 MODO SEGURANÇA — ATIVADO!")
    logger.info("═══════════════════════════════════════════")

    # Criar janela e forçar que fique visível no topo
    window_name = "JARVIS SECURITY"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    try:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    # ── Variáveis do loop ────────────────────────────────────
    intruso_counter = 0            # Frames consecutivos com intruso
    frame_count = 0
    fps = 0.0
    fps_timer = time.time()
    last_faces = []                # Cache de rostos do último processamento
    last_persons = []              # Cache de pessoas do último processamento

    # ── Loop ─────────────────────────────────────────────────
    while _seguranca_ativa:
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, 1)
        frame_count += 1
        now = time.time()

        # Calcular FPS
        if now - fps_timer >= 1.0:
            fps = frame_count / (now - fps_timer)
            frame_count = 0
            fps_timer = now

        # ── Processar a cada N frames (performance) ──────────
        if frame_count % _PROCESS_EVERY_N_FRAMES == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 1. Detectar pessoas
            last_persons = detector.detectar(frame)

            # 2. Reconhecer rostos
            last_faces = recognizer.reconhecer(frame, rgb)

            # 3. Lógica de intruso
            has_intruso = False
            for rosto in last_faces:
                if not rosto["autorizado"]:
                    has_intruso = True
                    break

            if has_intruso:
                intruso_counter += 1

                # Verificar threshold de frames consecutivos
                if intruso_counter >= _INTRUSO_FRAMES_THRESHOLD:
                    # INTRUSO CONFIRMADO!
                    _alert_system.disparar_alerta(frame, "DESCONHECIDO")
                    intruso_counter = 0  # Reset para próximo ciclo
            else:
                # Sem intruso — resetar contador
                if intruso_counter > 0:
                    intruso_counter = max(0, intruso_counter - 2)  # Decay gradual

        # ── Desenhar HUD ─────────────────────────────────────
        _draw_security_hud(
            frame,
            pessoas=last_persons,
            rostos=last_faces,
            intruso_count=intruso_counter,
            fps=fps,
            alarme_ativo=_alert_system.is_alarm_playing,
            total_alertas=_alert_system.total_alerts,
        )

        # ── Exibir ───────────────────────────────────────────
        cv2.imshow(window_name, frame)

        # ── Teclas ───────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            logger.info("[Segurança] Tecla Q — encerrando")
            break
        elif key == 27:  # ESC = parar alarme
            _alert_system.parar_alarme()

    # ═══════════════════════════════════════════════════════════
    #  Cleanup
    # ═══════════════════════════════════════════════════════════

    logger.info("[Segurança] Encerrando subsistemas...")

    _alert_system.parar_alarme()
    recognizer.stop()
    detector.stop()
    cap.release()

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

    _seguranca_ativa = False

    logger.info(
        f"[Segurança] 📊 Alertas: {_alert_system.total_alerts} | "
        f"Fotos: {_alert_system.total_photos}"
    )
    logger.info("═══════════════════════════════════════════")
    logger.info("  🟢 MODO SEGURANÇA — DESATIVADO")
    logger.info("═══════════════════════════════════════════")


# ═══════════════════════════════════════════════════════════════
#  API Pública
# ═══════════════════════════════════════════════════════════════

def iniciar_seguranca() -> str:
    """
    Ativa o modo de segurança com câmera.
    Inicia webcam, detecção de pessoas e reconhecimento facial.

    Returns:
        Mensagem de status.
    """
    global _seguranca_ativa, _thread_seguranca

    if _seguranca_ativa:
        return "🔴 Modo segurança já está **ATIVO**!"

    if not _deps_minimos_ok():
        return (
            "❌ OpenCV não instalado.\n"
            "Execute: `pip install opencv-python`"
        )

    _seguranca_ativa = True
    _thread_seguranca = threading.Thread(target=_loop_seguranca, daemon=True)
    _thread_seguranca.start()

    deps = _verificar_deps()
    deps_text = "\n".join(f"  {v}" for v in deps.values())

    return (
        "🔴 **MODO SEGURANÇA — ATIVADO!**\n\n"
        "📷 Webcam monitorando em tempo real\n"
        "🧑 Detectando pessoas automaticamente\n"
        "👤 Reconhecimento facial ativo\n\n"
        "⚠️ **Alertas:**\n"
        f"  • Intruso confirmado após {_INTRUSO_FRAMES_THRESHOLD} frames\n"
        f"  • Alarme: alarme.mp3 em loop\n"
        f"  • Fotos salvas em data/security/intrusions/\n\n"
        "⏹️ Pressione **Q** para sair | **ESC** para parar alarme\n\n"
        f"📦 **Backends:**\n{deps_text}"
    )


def parar_seguranca() -> str:
    """Para o modo de segurança."""
    global _seguranca_ativa

    if not _seguranca_ativa:
        return "🟢 Modo segurança já está **desativado**."

    _seguranca_ativa = False

    # Parar alarme se tocando
    if _alert_system:
        _alert_system.parar_alarme()

    return "🟢 Modo segurança **DESATIVADO**."


def status_seguranca() -> str:
    """Retorna status completo do sistema de segurança."""
    linhas = ["📊 **Status do Sistema de Segurança**\n"]

    # Status geral
    if _seguranca_ativa:
        linhas.append("  🔴 Modo segurança: **ATIVO**")
    else:
        linhas.append("  🟢 Modo segurança: **INATIVO**")

    # Alarme
    if _alert_system and _alert_system.is_alarm_playing:
        linhas.append("  🔊 Alarme: **TOCANDO**")
    else:
        linhas.append("  🔇 Alarme: parado")

    # Alertas
    if _alert_system:
        linhas.append(f"  🚨 Total alertas: {_alert_system.total_alerts}")
        linhas.append(f"  📸 Fotos capturadas: {_alert_system.total_photos}")

    # Cadastro
    if _face_register:
        linhas.append(f"\n  👤 Usuários cadastrados: {_face_register.num_usuarios}")
        linhas.append(f"  🧠 Backend facial: {_face_register.backend}")

    # Deps
    linhas.append("\n📦 **Dependências:**")
    deps = _verificar_deps()
    for info in deps.values():
        linhas.append(f"  {info}")

    return "\n".join(linhas)


def cadastrar_rosto(nome: str, num_amostras: int = 10) -> str:
    """
    Cadastra rosto de um usuário autorizado via webcam.

    Args:
        nome: Nome do usuário (ex: "Gui").
        num_amostras: Número de capturas faciais.

    Returns:
        Mensagem de status do cadastro.
    """
    global _face_register

    if _face_register is None:
        from .security_system.face_register import FaceRegister
        _face_register = FaceRegister()

    return _face_register.cadastrar_via_webcam(nome, num_amostras)


def cadastrar_rosto_imagem(nome: str, caminho: str) -> str:
    """Cadastra rosto a partir de imagem."""
    global _face_register

    if _face_register is None:
        from .security_system.face_register import FaceRegister
        _face_register = FaceRegister()

    return _face_register.cadastrar_via_imagem(nome, caminho)


def listar_rostos() -> str:
    """Lista todos os rostos cadastrados."""
    global _face_register

    if _face_register is None:
        from .security_system.face_register import FaceRegister
        _face_register = FaceRegister()

    return _face_register.listar_usuarios()


def remover_rosto(nome: str) -> str:
    """Remove um rosto cadastrado."""
    global _face_register

    if _face_register is None:
        from .security_system.face_register import FaceRegister
        _face_register = FaceRegister()

    return _face_register.remover_usuario(nome)


def parar_alarme() -> str:
    """Para o alarme manualmente."""
    if _alert_system:
        return _alert_system.parar_alarme()
    return "🔇 Nenhum alarme ativo."


def historico_intrusoes() -> str:
    """Retorna histórico de intrusões da sessão."""
    if _alert_system:
        return _alert_system.historico_intrusoes()
    return "📋 Sistema de segurança não foi iniciado nesta sessão."
