# ═══════════════════════════════════════════════════════════════
#  JARVIS SECURITY SYSTEM — Segurança Inteligente com Câmera
# ═══════════════════════════════════════════════════════════════
#
#  Submódulos:
#    face_register      → Cadastro de rostos autorizados
#    face_recognizer    → Reconhecimento facial em tempo real
#    person_detector    → Detecção de pessoas (YOLO / HOG)
#    alert_system       → Alarme, captura de fotos, notificações
#
#  Fluxo:
#    1. Ativação por voz ou agent tool
#    2. Webcam captura frames em tempo real
#    3. YOLO detecta pessoas no ambiente
#    4. Face recognition identifica: AUTORIZADO vs INTRUSO
#    5. Se intruso confirmado (10+ frames) → alarme + foto
#
#  Ativação por voz:
#    "Jarvis, ative o modo alerta de segurança"
#    "Jarvis, desative o modo alerta de segurança"
# ═══════════════════════════════════════════════════════════════
