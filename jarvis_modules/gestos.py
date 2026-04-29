"""
═══════════════════════════════════════════════════════════════
  JARVIS GESTURE CONTROL ENGINE v4.1
  Controle Híbrido: Gestos + Pinça + Punho + Voz
═══════════════════════════════════════════════════════════════

  Sistema de controle do computador em tempo real usando:
    🎤 Voz (SpeechRecognition) → Ativar/desativar sistema
    🖐 Gestos (MediaPipe)      → Controlar cursor/janelas
    🤏 Pinça (MediaPipe)       → Cliques e Drag (polegar + indicador)

  Mapeamento completo:
    🖐 Mão aberta       → Movimento do cursor (com suavização)
    👌 OK               → Modo especial (trocar abas com mov. lateral)
    ☝️ Apontar          → Cursor preciso (sem aceleração)
    ✌️ Paz (V)          → Screenshot
    🤙 Scroll           → Scroll vertical
    🤏 Pinça rápida     → Clique simples (abrir e fechar rápido)
    🤏 Pinça segurando  → Drag and Drop (segurar = segurar clique)
    ✊ Punho             → Drag and Drop (alternativa à pinça)

  RESTAURADO na v4.1:
    ✊ Punho             → Drag and Drop (de volta como alternativa)

  Segurança:
    • Timeout automático se nenhuma mão detectada (30s)
    • Desativação por voz ou tecla Q
    • Debounce em todos os gestos

  Multi-monitor:
    • ctypes GetSystemMetrics para área virtual completa
    • SetCursorPos para mover cursor entre monitores

  Ativação por voz:
    "Jarvis, ative o controle de gesto"
    "Jarvis, desative o controle de gesto"
"""

import time
import threading
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Estado Global
# ═══════════════════════════════════════════════════════════════

_controle_ativo = False
_voice_ativo = False
_thread_gestos = None
_thread_voice = None

# Sub-sistemas (instanciados sob demanda)
_voice_controller = None
_pinch_detector = None  # PinchClickDetector — cliques e drag via pinça

# Configurações
_TIMEOUT_SEM_MAO = 30       # Segundos sem detectar mão → desativa
_FPS_DISPLAY = True          # Mostrar FPS no preview


# ═══════════════════════════════════════════════════════════════
#  Verificação de Dependências
# ═══════════════════════════════════════════════════════════════

def _verificar_deps() -> dict:
    """Verifica todas as dependências. Retorna dict com status."""
    status = {}

    try:
        import cv2
        status["opencv"] = f"✅ OpenCV {cv2.__version__}"
    except ImportError:
        status["opencv"] = "❌ opencv-python"

    try:
        import mediapipe as mp
        status["mediapipe"] = f"✅ MediaPipe {mp.__version__}"
    except ImportError:
        status["mediapipe"] = "❌ mediapipe"

    try:
        import pyautogui
        status["pyautogui"] = f"✅ PyAutoGUI {pyautogui.__version__}"
    except ImportError:
        status["pyautogui"] = "❌ pyautogui"

    try:
        import speech_recognition as sr
        status["speech"] = f"✅ SpeechRecognition {sr.__version__}"
    except ImportError:
        status["speech"] = "⚠️ SpeechRecognition (voz desabilitada)"

    return status


def _deps_minimos_ok() -> bool:
    """Verifica se as dependências mínimas estão instaladas."""
    try:
        import cv2
        import mediapipe
        import pyautogui
        return True
    except ImportError:
        return False


# ═══════════════════════════════════════════════════════════════
#  HUD / Overlay Visual
# ═══════════════════════════════════════════════════════════════

def _draw_hud(frame, gesture: str, pinch_event: str, pinch_time: float,
              fps: float, ok_mode: bool, dragging: bool, scroll_mode: bool,
              timeout_counter: float, is_pinching: bool = False,
              is_dragging_pinch: bool = False):
    """Desenha HUD informativo sobre o frame da câmera."""
    import cv2

    h, w = frame.shape[:2]

    # ── Fundo semi-transparente no topo ──────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 110), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # ── Título ───────────────────────────────────────────────
    cv2.putText(
        frame, "JARVIS — Controle por Gestos v4",
        (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2,
    )

    # ── Status ATIVO ─────────────────────────────────────────
    cv2.putText(
        frame, "STATUS: ATIVO",
        (w - 220, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
    )

    # ── Gesto detectado ──────────────────────────────────────
    gesture_icons = {
        "mao_aberta": "OPEN HAND - Cursor",
        "ok": "OK - Tab Mode",
        "apontar": "POINT - Precision",
        "paz": "PEACE - Screenshot",
        "scroll": "SCROLL - Mouse Wheel",
        "punho": "FIST - Drag",
        "desconhecido": "---",
    }
    gesture_display = gesture_icons.get(gesture, gesture)

    # Cor baseada no gesto
    gesture_colors = {
        "mao_aberta": (0, 255, 0),      # Verde
        "ok": (255, 200, 0),             # Ciano
        "apontar": (255, 255, 0),        # Amarelo
        "paz": (0, 255, 255),            # Ciano claro
        "scroll": (200, 150, 255),       # Lilás
        "punho": (0, 100, 255),          # Laranja/Vermelho (drag)
    }
    color = gesture_colors.get(gesture, (200, 200, 200))

    cv2.putText(
        frame, f"Gesto: {gesture_display}",
        (15, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
    )

    # ── Evento de pinça ──────────────────────────────────────
    if is_dragging_pinch:
        cv2.putText(
            frame, "PINCH DRAG (segurando)",
            (15, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 100, 255), 2,
        )
    elif is_pinching:
        cv2.putText(
            frame, "PINCH...",
            (15, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2,
        )
    elif pinch_event and (time.time() - pinch_time) < 2.0:
        if pinch_event == "🤏":
            pinch_display = "Pinch: CLIQUE!"
            pinch_color = (0, 200, 255)
        elif pinch_event == "🤏✊":
            pinch_display = "Pinch: DRAG INICIADO!"
            pinch_color = (0, 100, 255)
        elif pinch_event == "🤏↑":
            pinch_display = "Pinch: DRAG SOLTO!"
            pinch_color = (0, 255, 150)
        else:
            pinch_display = f"Pinch: {pinch_event}"
            pinch_color = (200, 200, 200)
        cv2.putText(
            frame, pinch_display,
            (15, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.6, pinch_color, 2,
        )

    # ── Indicadores de modo ──────────────────────────────────
    indicators = []
    if ok_mode:
        indicators.append(("OK MODE", (255, 200, 0)))
    if dragging or is_dragging_pinch:
        indicators.append(("DRAGGING", (0, 100, 255)))
    if scroll_mode:
        indicators.append(("SCROLL MODE", (200, 150, 255)))

    for i, (label, col) in enumerate(indicators):
        x_pos = w - 200
        y_pos = 58 + i * 25
        cv2.putText(
            frame, label,
            (x_pos, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2,
        )

    # ── FPS ──────────────────────────────────────────────────
    if _FPS_DISPLAY:
        cv2.putText(
            frame, f"FPS: {fps:.0f}",
            (w - 120, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1,
        )

    # ── Barra de timeout ─────────────────────────────────────
    if timeout_counter > 0:
        pct = min(1.0, timeout_counter / _TIMEOUT_SEM_MAO)
        bar_w = int(200 * pct)
        bar_color = (
            int(255 * pct),       # Vermelho aumenta
            int(255 * (1 - pct)), # Verde diminui
            0,
        )
        cv2.rectangle(frame, (15, h - 25), (15 + bar_w, h - 15), bar_color, -1)
        cv2.rectangle(frame, (15, h - 25), (215, h - 15), (100, 100, 100), 1)
        cv2.putText(
            frame, "Timeout",
            (220, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1,
        )

    # ── Instruções no rodapé ─────────────────────────────────
    cv2.putText(
        frame, "Pressione Q para sair",
        (w - 220, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1,
    )


# ═══════════════════════════════════════════════════════════════
#  Loop Principal de Controle por Gestos
# ═══════════════════════════════════════════════════════════════

def _loop_gestos():
    """
    Loop principal que orquestra todos os subsistemas.
    Roda em thread daemon.
    """
    global _controle_ativo, _pinch_detector

    # ── Imports locais ───────────────────────────────────────
    try:
        import cv2
    except ImportError:
        logger.error("[Gestos] OpenCV não disponível")
        _controle_ativo = False
        return

    from .gesture_system.camera import Camera
    from .gesture_system.hand_tracking import HandTracker
    from .gesture_system.gesture_recognition import GestureRecognizer
    from .gesture_system.actions import GestureActions

    # ── Inicializar sub-sistemas ─────────────────────────────
    camera = Camera(device_id=0, width=640, height=480, fps=30)
    tracker = HandTracker(max_hands=1, detection_confidence=0.7, tracking_confidence=0.5)
    recognizer = GestureRecognizer(debounce_frames=3)
    actions = GestureActions(smoothing_window=5)

    if not camera.start():
        logger.error("[Gestos] Falha ao abrir webcam")
        _controle_ativo = False
        return

    if not tracker.start():
        logger.error("[Gestos] Falha ao iniciar MediaPipe")
        camera.stop()
        _controle_ativo = False
        return

    # ── Iniciar detecção de pinça (cliques + drag) ───────────
    pinch_available = False
    try:
        from .gesture_system.pinch_click import PinchClickDetector

        _pinch_detector = PinchClickDetector(
            pinch_threshold=0.045,
            release_threshold=0.065,
            drag_time=0.30,         # ~300ms segurando = drag
            cooldown=0.25,
        )
        # Conectar callbacks de pinça → ações
        _pinch_detector.on_click = actions.left_click           # 🤏 rápida → clique
        _pinch_detector.on_drag_start = actions.start_drag      # 🤏 segurando → drag
        _pinch_detector.on_drag_end = actions.stop_drag         # 🤏 soltar → soltar drag
        pinch_available = True
        logger.info("[Gestos] 🤏 Detecção de PINÇA v2 ativada (Clique + Drag)")
    except Exception as e:
        logger.warning(f"[Gestos] Pinça desabilitada: {e}")

    logger.info("═══════════════════════════════════════════")
    logger.info("  🖐 CONTROLE POR GESTOS v4 — ATIVADO!")
    logger.info("═══════════════════════════════════════════")

    # ── Variáveis do loop ────────────────────────────────────
    current_gesture = ""
    last_hand_time = time.time()
    frame_count = 0
    fps = 0.0
    fps_timer = time.time()

    # Criar janela visível e no topo
    gesture_window = "JARVIS - Controle por Gestos"
    cv2.namedWindow(gesture_window, cv2.WINDOW_AUTOSIZE)
    try:
        cv2.setWindowProperty(gesture_window, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    # ── Loop principal ───────────────────────────────────────
    while _controle_ativo:
        ret, frame, rgb = camera.read()
        if not ret:
            logger.warning("[Gestos] Frame perdido")
            continue

        # ── Calcular FPS ─────────────────────────────────────
        frame_count += 1
        now = time.time()
        if now - fps_timer >= 1.0:
            fps = frame_count / (now - fps_timer)
            frame_count = 0
            fps_timer = now

        # ── Processar mãos ───────────────────────────────────
        results = tracker.process(rgb)
        hand_detected = False

        if results and results.multi_hand_landmarks:
            for hand_lm in results.multi_hand_landmarks:
                hand_detected = True
                last_hand_time = now

                # Desenhar landmarks
                tracker.draw_landmarks(frame, hand_lm)

                # Reconhecer gesto (v3: sem punho)
                gesture, fingers, confirmed, extra = recognizer.recognize(hand_lm)
                current_gesture = gesture

                # ── Atualizar detector de pinça (SEMPRE, cada frame) ──
                # Deve rodar ANTES do debounce para não perder frames.
                # A pinça funciona INDEPENDENTE do gesto classificado.
                thumb_tip = hand_lm.landmark[4]
                index_tip = hand_lm.landmark[8]
                if _pinch_detector:
                    _pinch_detector.update(thumb_tip, index_tip)

                if not confirmed:
                    continue

                # ── Obter posição da mão ────────────────────────
                wrist = hand_lm.landmark[0]
                hand_x = index_tip.x
                hand_y = index_tip.y
                speed = extra.get("speed", 0.0)

                # ── Executar ação baseada no gesto ─────────────
                # NOTA: Drag/clique agora é feito pela pinça, não pelo gesto.
                # Os gestos abaixo controlam apenas cursor e modos.

                if gesture == GestureRecognizer.OPEN_HAND:
                    # 🖐 Mão aberta → mover cursor (com aceleração)
                    actions.exit_ok_mode()
                    actions.exit_scroll_mode()
                    actions.move_cursor(hand_x, hand_y, speed)

                elif gesture == GestureRecognizer.OK:
                    # 👌 OK → trocar abas
                    actions.exit_scroll_mode()
                    actions.enter_ok_mode(hand_x)
                    actions.process_ok_mode(hand_x)

                elif gesture == GestureRecognizer.POINT:
                    # ☝️ Apontar → cursor preciso (sem aceleração)
                    actions.exit_ok_mode()
                    actions.exit_scroll_mode()
                    actions.move_cursor(hand_x, hand_y)

                elif gesture == GestureRecognizer.PEACE:
                    # ✌️ Paz (V) → screenshot
                    actions.exit_ok_mode()
                    actions.exit_scroll_mode()
                    actions.take_screenshot()

                elif gesture == GestureRecognizer.SCROLL:
                    # 🤙 Scroll → scroll vertical
                    actions.exit_ok_mode()
                    actions.enter_scroll_mode(hand_y)
                    actions.process_scroll(hand_y)

                elif gesture == GestureRecognizer.FIST:
                    # ✊ Punho → Drag and Drop (alternativa à pinça)
                    actions.exit_ok_mode()
                    actions.exit_scroll_mode()
                    actions.start_drag()
                    # Continua movendo cursor enquanto arrasta
                    actions.move_cursor(hand_x, hand_y, speed)

                else:
                    # Gesto desconhecido
                    # Se não é punho, soltar drag de punho (se ativo)
                    if actions.is_dragging and not (
                        _pinch_detector and _pinch_detector.is_currently_dragging
                    ):
                        actions.stop_drag()
                    actions.move_cursor(hand_x, hand_y, speed)

        # ── Timeout: nenhuma mão detectada ───────────────────
        if not hand_detected:
            time_without_hand = now - last_hand_time

            # Soltar drag se mão sumiu
            if time_without_hand > 1.0:
                actions.stop_drag()
                actions.exit_ok_mode()
                actions.exit_scroll_mode()

            # Auto-desativar após timeout
            if time_without_hand > _TIMEOUT_SEM_MAO:
                logger.info(
                    f"[Gestos] ⏰ Timeout: {_TIMEOUT_SEM_MAO}s sem mão detectada. "
                    "Desativando..."
                )
                break
        else:
            last_hand_time = now

        # ── Obter evento de pinça para HUD ───────────────────
        pinch_event = ""
        pinch_time = 0.0
        is_pinching = False
        is_dragging_pinch = False
        if pinch_available and _pinch_detector:
            pinch_event = _pinch_detector.last_event
            pinch_time = _pinch_detector.last_event_time
            is_pinching = _pinch_detector.is_currently_pinching
            is_dragging_pinch = _pinch_detector.is_currently_dragging

        # ── Desenhar HUD ─────────────────────────────────────
        timeout_counter = 0.0
        if not hand_detected:
            timeout_counter = now - last_hand_time

        _draw_hud(
            frame,
            gesture=current_gesture,
            pinch_event=pinch_event,
            pinch_time=pinch_time,
            fps=fps,
            ok_mode=actions.is_ok_mode,
            dragging=actions.is_dragging,
            scroll_mode=actions.is_scroll_mode,
            timeout_counter=timeout_counter,
            is_pinching=is_pinching,
            is_dragging_pinch=is_dragging_pinch,
        )

        # ── Exibir preview ───────────────────────────────────
        cv2.imshow(gesture_window, frame)

        # ── Tecla Q para sair ────────────────────────────────
        if cv2.waitKey(1) & 0xFF == ord("q"):
            logger.info("[Gestos] Tecla Q pressionada — encerrando")
            break

    # ═══════════════════════════════════════════════════════════
    #  Cleanup
    # ═══════════════════════════════════════════════════════════

    logger.info("[Gestos] Encerrando subsistemas...")

    # Resetar ações (soltar drag, sair do OK mode)
    actions.reset()

    # Parar detecção de pinça
    if _pinch_detector:
        _pinch_detector.reset()
        _pinch_detector = None

    # Parar tracking e câmera
    tracker.stop()
    camera.stop()

    # Fechar janela OpenCV
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

    _controle_ativo = False

    # Log de estatísticas
    logger.info(f"[Gestos] {actions.stats()}")
    logger.info("═══════════════════════════════════════════")
    logger.info("  ⏹ CONTROLE POR GESTOS v4 — DESATIVADO")
    logger.info("═══════════════════════════════════════════")


# ═══════════════════════════════════════════════════════════════
#  Handlers de Voz → Gestos
# ═══════════════════════════════════════════════════════════════

def _on_voice_activate():
    """Callback: voz detectou comando de ativação."""
    iniciar_controle_gestos()


def _on_voice_deactivate():
    """Callback: voz detectou comando de desativação."""
    parar_controle_gestos()


# ═══════════════════════════════════════════════════════════════
#  API Pública
# ═══════════════════════════════════════════════════════════════

def iniciar_controle_gestos() -> str:
    """
    Inicia o sistema de controle por gestos.
    Ativa webcam, MediaPipe, detecção de pinça e feedback visual.
    Suporte multi-monitor via ctypes.

    Returns:
        Mensagem de status.
    """
    global _controle_ativo, _thread_gestos

    if _controle_ativo:
        return "🖐️ Controle por gestos já está **ATIVO**!"

    if not _deps_minimos_ok():
        deps = _verificar_deps()
        faltando = [v for v in deps.values() if v.startswith("❌")]
        return (
            "❌ Dependências mínimas ausentes:\n"
            + "\n".join(faltando) + "\n\n"
            "Execute: `pip install opencv-python mediapipe pyautogui`"
        )

    _controle_ativo = True
    _thread_gestos = threading.Thread(target=_loop_gestos, daemon=True)
    _thread_gestos.start()

    # Verificar extras
    deps = _verificar_deps()
    extras = []
    if "⚠️" in deps.get("speech", ""):
        extras.append("  ⚠️ SpeechRecognition ausente — voz desabilitada")
    extras_text = "\n".join(extras) if extras else ""

    return (
        "🖐️ **Controle por Gestos v4.1 — ATIVADO!**\n\n"
        "🎮 **Gestos de Mão:**\n"
        "  🖐 Mão aberta → Mover cursor\n"
        "  👌 OK → Modo abas (mova para os lados)\n"
        "  ☝️ Apontar → Cursor preciso\n"
        "  ✌️ V → Screenshot\n"
        "  🤙 2 dedos → Scroll\n\n"
        "🤏 **Pinça (Polegar + Indicador):**\n"
        "  🤏 Pinça rápida (abrir e fechar) → Clique Simples\n"
        "  🤏 Pinça segurando (manter fechada) → Drag and Drop\n\n"
        "✊ **Punho (Mão fechada) — RESTAURADO:**\n"
        "  ✊ Fechar mão → Drag and Drop (alternativa à pinça)\n"
        "  🖐 Abrir mão → Soltar o drag\n\n"
        "📺 **Multi-Monitor:** Suporte total a 2+ monitores\n\n"
        "⏹️ Pressione **Q** na janela ou diga "
        "'Jarvis, desative o controle de gesto' para encerrar.\n"
        f"⏰ Auto-desliga após {_TIMEOUT_SEM_MAO}s sem mão detectada.\n"
        + (f"\n{extras_text}" if extras_text else "")
    )


def parar_controle_gestos() -> str:
    """
    Para o sistema de controle por gestos.
    Encerra webcam, tracking e detecção de pinça.

    Returns:
        Mensagem de status.
    """
    global _controle_ativo

    if not _controle_ativo:
        return "💤 Controle por gestos já está **desativado**."

    _controle_ativo = False
    return "⏹️ Controle por gestos **DESATIVADO**."


def status_gestos() -> str:
    """
    Retorna status completo do sistema de gestos.

    Returns:
        Relatório de status com todos os subsistemas.
    """
    status_lines = ["📊 **Status do Sistema de Gestos v4.1**\n"]

    # Controle de gestos
    if _controle_ativo:
        status_lines.append("  🖐 Controle por gestos: **ATIVO** ✅")
    else:
        status_lines.append("  🖐 Controle por gestos: **INATIVO** 💤")

    # Detecção de pinça
    if _pinch_detector:
        status_lines.append("  🤏 Detecção de pinça: **ATIVA** ✅")
    else:
        status_lines.append("  🤏 Detecção de pinça: **INATIVA** 💤")

    # Controle por voz
    if _voice_controller and _voice_controller.is_running:
        status_lines.append("  🎤 Controle por voz: **ATIVO** ✅")
    else:
        status_lines.append("  🎤 Controle por voz: **INATIVO** 💤")

    # Dependências
    status_lines.append("\n📦 **Dependências:**")
    deps = _verificar_deps()
    for dep, info in deps.items():
        status_lines.append(f"  {info}")

    return "\n".join(status_lines)


def iniciar_voice_listener() -> str:
    """
    Inicia o listener de voz para ativação/desativação remota.
    O listener fica em background escutando:
      "Jarvis, ative o controle de gesto"
      "Jarvis, desative o controle de gesto"

    Returns:
        Mensagem de status.
    """
    global _voice_controller, _voice_ativo

    if _voice_ativo and _voice_controller and _voice_controller.is_running:
        return "🎤 Voice listener já está **ATIVO**!"

    try:
        from .gesture_system.voice_control import VoiceController
    except ImportError:
        return "❌ SpeechRecognition não disponível. Execute: pip install SpeechRecognition"

    _voice_controller = VoiceController(language="pt-BR")
    _voice_controller.on_activate = _on_voice_activate
    _voice_controller.on_deactivate = _on_voice_deactivate
    _voice_controller.start()
    _voice_ativo = True

    return (
        "🎤 **Voice Listener — ATIVADO!**\n\n"
        "Diga:\n"
        '  "Jarvis, ative o controle de gesto" → Liga gestos\n'
        '  "Jarvis, desative o controle de gesto" → Desliga gestos\n'
    )


def parar_voice_listener() -> str:
    """Para o listener de voz."""
    global _voice_controller, _voice_ativo

    if not _voice_ativo or not _voice_controller:
        return "💤 Voice listener já está desativado."

    _voice_controller.stop()
    _voice_ativo = False
    return "⏹️ Voice listener **DESATIVADO**."


def iniciar_sistema_completo() -> str:
    """
    Inicia TODO o sistema híbrido:
    1. Voice listener (ativação por voz)
    2. Controle por gestos + pinça

    Returns:
        Mensagem de status completa.
    """
    msgs = []

    # Iniciar voice listener
    voice_msg = iniciar_voice_listener()
    msgs.append(voice_msg)

    # Iniciar gestos + pinça
    gestos_msg = iniciar_controle_gestos()
    msgs.append(gestos_msg)

    return "\n\n".join(msgs)


def parar_sistema_completo() -> str:
    """
    Para TODO o sistema híbrido.

    Returns:
        Mensagem de status.
    """
    msgs = []

    gestos_msg = parar_controle_gestos()
    msgs.append(gestos_msg)

    voice_msg = parar_voice_listener()
    msgs.append(voice_msg)

    return "\n".join(msgs)
