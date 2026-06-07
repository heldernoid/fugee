"""app/interview_script.py — the fixed, multilingual interview script.

The interview is fully deterministic: a fixed ordered set of questions, each with
a fixed answer control, pre-translated into every supported language. The LLM is
NOT used to phrase questions (that caused inconsistent controls, wrong/repeated
questions, and drift). Questions may template in already-collected values, e.g.
"what happened in {origin}".

Translations are authored here (short UI strings) so behaviour is identical every
run, in every language, with no model variance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.state.session import State


@dataclass
class Question:
    sid: str            # string id (key into translations)
    field: str          # session.interview attribute to fill
    phase: State
    control: str        # "country" | "yesno" | "choice" | "text"
    kind: str = "str"   # str | bool | list | list_text
    options: list = field(default_factory=list)  # option string-ids for choice/yesno
    alt_sid: str | None = None       # alternate text when still in country of origin
    skip_if_in_origin: bool = False  # skip when current country == origin


# Ordered interview plan. Controls are fixed; some questions template {origin}.
QUESTIONS: list[Question] = [
    Question("q_current", "current_country", State.SITUATION, "country"),
    Question("q_origin", "origin_country", State.SITUATION, "country"),
    Question("q_reason", "free_text_history", State.SITUATION, "text", alt_sid="q_reason_instill"),
    Question("q_danger", "immediate_danger", State.SITUATION, "yesno", kind="bool"),
    Question("q_duration", "displacement_duration", State.HISTORY, "text", skip_if_in_origin=True),
    Question("q_documents", "documents_available", State.HISTORY, "choice", kind="list",
             options=["opt_passport", "opt_id", "opt_birth", "opt_none", "opt_other"]),
    Question("q_languages", "languages_spoken", State.GOALS, "text", kind="list_text"),
    Question("q_destination", "destination_preferences", State.GOALS, "text", kind="list_text"),
]
REVIEW_INDEX = len(QUESTIONS)

# Supported languages are keyed by the English name stored in session.language.
TR: dict[str, dict[str, str]] = {
    "English": {
        "welcome": "Hello — I'm here to help, and we'll go one step at a time.",
        "q_current": "Which country are you currently in?",
        "q_origin": "Which country are you originally from?",
        "q_reason": "Can you tell me what happened in {origin} that made you leave?",
        "q_danger": "Are you in immediate danger right now?",
        "q_duration": "How long ago did you leave {origin}?",
        "q_documents": "Which identity or travel documents do you still have?",
        "q_languages": "Which languages do you speak?",
        "q_destination": "Is there a country where you have family or community, or would prefer to seek safety?",
        "review_intro": "Here is what I understood:",
        "review_confirm": "Is this correct?",
        "review_yes": "Yes, that's correct",
        "review_no": "Something needs changing",
        "opt_yes": "Yes", "opt_no": "No",
        "opt_passport": "Passport", "opt_id": "National ID", "opt_birth": "Birth certificate",
        "opt_none": "None", "opt_other": "Other",
        "ui_answer": "Your answer", "ui_continue": "Continue",
    },
    "French": {
        "welcome": "Bonjour — je suis là pour vous aider, nous avancerons étape par étape.",
        "q_current": "Dans quel pays vous trouvez-vous actuellement ?",
        "q_origin": "De quel pays êtes-vous originaire ?",
        "q_reason": "Pouvez-vous me dire ce qui s'est passé en {origin} qui vous a poussé à partir ?",
        "q_danger": "Êtes-vous en danger immédiat en ce moment ?",
        "q_duration": "Il y a combien de temps avez-vous quitté {origin} ?",
        "q_documents": "Quels documents d'identité ou de voyage avez-vous encore ?",
        "q_languages": "Quelles langues parlez-vous ?",
        "q_destination": "Y a-t-il un pays où vous avez de la famille ou une communauté, ou que vous préféreriez pour demander l'asile ?",
        "review_intro": "Voici ce que j'ai compris :",
        "review_confirm": "Est-ce exact ?",
        "review_yes": "Oui, c'est exact",
        "review_no": "Quelque chose doit être corrigé",
        "opt_yes": "Oui", "opt_no": "Non",
        "opt_passport": "Passeport", "opt_id": "Carte d'identité", "opt_birth": "Acte de naissance",
        "opt_none": "Aucun", "opt_other": "Autre",
        "ui_answer": "Votre réponse", "ui_continue": "Continuer",
    },
    "Spanish": {
        "welcome": "Hola — estoy aquí para ayudarte, iremos paso a paso.",
        "q_current": "¿En qué país te encuentras actualmente?",
        "q_origin": "¿De qué país eres originario?",
        "q_reason": "¿Puedes contarme qué pasó en {origin} que te hizo huir?",
        "q_danger": "¿Estás en peligro inmediato en este momento?",
        "q_duration": "¿Hace cuánto tiempo saliste de {origin}?",
        "q_documents": "¿Qué documentos de identidad o de viaje conservas?",
        "q_languages": "¿Qué idiomas hablas?",
        "q_destination": "¿Hay algún país donde tengas familia o comunidad, o que prefieras para buscar protección?",
        "review_intro": "Esto es lo que entendí:",
        "review_confirm": "¿Es correcto?",
        "review_yes": "Sí, es correcto",
        "review_no": "Algo debe cambiar",
        "opt_yes": "Sí", "opt_no": "No",
        "opt_passport": "Pasaporte", "opt_id": "Documento de identidad", "opt_birth": "Partida de nacimiento",
        "opt_none": "Ninguno", "opt_other": "Otro",
        "ui_answer": "Tu respuesta", "ui_continue": "Continuar",
    },
    "Portuguese": {
        "welcome": "Olá — estou aqui para ajudar, vamos passo a passo.",
        "q_current": "Em que país você está atualmente?",
        "q_origin": "De que país você é originário?",
        "q_reason": "Pode me contar o que aconteceu em {origin} que fez você sair?",
        "q_danger": "Você está em perigo imediato neste momento?",
        "q_duration": "Há quanto tempo você saiu de {origin}?",
        "q_documents": "Quais documentos de identidade ou de viagem você ainda tem?",
        "q_languages": "Quais idiomas você fala?",
        "q_destination": "Existe algum país onde você tem família ou comunidade, ou que prefira para buscar proteção?",
        "review_intro": "Foi isto que entendi:",
        "review_confirm": "Está correto?",
        "review_yes": "Sim, está correto",
        "review_no": "Algo precisa mudar",
        "opt_yes": "Sim", "opt_no": "Não",
        "opt_passport": "Passaporte", "opt_id": "Documento de identidade", "opt_birth": "Certidão de nascimento",
        "opt_none": "Nenhum", "opt_other": "Outro",
        "ui_answer": "Sua resposta", "ui_continue": "Continuar",
    },
    "Arabic": {
        "welcome": "مرحباً — أنا هنا لمساعدتك، وسنتقدّم خطوة بخطوة.",
        "q_current": "في أي بلد توجد حالياً؟",
        "q_origin": "ما هو بلدك الأصلي؟",
        "q_reason": "هل يمكنك أن تخبرني بما حدث في {origin} ودفعك إلى المغادرة؟",
        "q_danger": "هل أنت في خطر مباشر الآن؟",
        "q_duration": "منذ متى غادرت {origin}؟",
        "q_documents": "ما هي وثائق الهوية أو السفر التي ما زلت تملكها؟",
        "q_languages": "ما هي اللغات التي تتحدثها؟",
        "q_destination": "هل هناك بلد لديك فيه عائلة أو مجتمع، أو تفضّله لطلب الحماية؟",
        "review_intro": "هذا ما فهمته:",
        "review_confirm": "هل هذا صحيح؟",
        "review_yes": "نعم، هذا صحيح",
        "review_no": "هناك ما يجب تغييره",
        "opt_yes": "نعم", "opt_no": "لا",
        "opt_passport": "جواز سفر", "opt_id": "بطاقة هوية", "opt_birth": "شهادة ميلاد",
        "opt_none": "لا شيء", "opt_other": "أخرى",
        "ui_answer": "إجابتك", "ui_continue": "متابعة",
    },
    "Hindi": {
        "welcome": "नमस्ते — मैं आपकी मदद के लिए यहाँ हूँ, हम एक-एक कदम बढ़ेंगे।",
        "q_current": "आप इस समय किस देश में हैं?",
        "q_origin": "आप मूल रूप से किस देश से हैं?",
        "q_reason": "क्या आप बता सकते हैं कि {origin} में क्या हुआ जिसकी वजह से आपको छोड़ना पड़ा?",
        "q_danger": "क्या आप अभी तत्काल खतरे में हैं?",
        "q_duration": "आपको {origin} छोड़े कितना समय हुआ?",
        "q_documents": "आपके पास अब भी कौन-कौन से पहचान या यात्रा दस्तावेज़ हैं?",
        "q_languages": "आप कौन-कौन सी भाषाएँ बोलते हैं?",
        "q_destination": "क्या कोई ऐसा देश है जहाँ आपका परिवार या समुदाय हो, या जहाँ आप सुरक्षा माँगना चाहेंगे?",
        "review_intro": "मैंने यह समझा है:",
        "review_confirm": "क्या यह सही है?",
        "review_yes": "हाँ, यह सही है",
        "review_no": "कुछ बदलना है",
        "opt_yes": "हाँ", "opt_no": "नहीं",
        "opt_passport": "पासपोर्ट", "opt_id": "राष्ट्रीय पहचान पत्र", "opt_birth": "जन्म प्रमाणपत्र",
        "opt_none": "कोई नहीं", "opt_other": "अन्य",
        "ui_answer": "आपका उत्तर", "ui_continue": "जारी रखें",
    },
    "Chinese": {
        "welcome": "您好——我在这里帮助您，我们会一步一步来。",
        "q_current": "您目前在哪个国家？",
        "q_origin": "您来自哪个国家？",
        "q_reason": "能告诉我在{origin}发生了什么让您不得不离开吗？",
        "q_danger": "您现在是否处于紧迫的危险中？",
        "q_duration": "您离开{origin}多久了？",
        "q_documents": "您还保有哪些身份或旅行证件？",
        "q_languages": "您会说哪些语言？",
        "q_destination": "有没有哪个国家您有家人或社群，或您更希望前往寻求保护？",
        "review_intro": "以下是我的理解：",
        "review_confirm": "这样对吗？",
        "review_yes": "对，没错",
        "review_no": "有些需要更改",
        "opt_yes": "是", "opt_no": "否",
        "opt_passport": "护照", "opt_id": "身份证", "opt_birth": "出生证明",
        "opt_none": "没有", "opt_other": "其他",
        "ui_answer": "您的回答", "ui_continue": "继续",
    },
    "Japanese": {
        "welcome": "こんにちは——お手伝いします。一つずつ進めましょう。",
        "q_current": "今どの国にいますか？",
        "q_origin": "もともとどの国の出身ですか？",
        "q_reason": "{origin}で何が起きて、離れることになったのか教えていただけますか？",
        "q_danger": "今、差し迫った危険にありますか？",
        "q_duration": "{origin}を離れてどのくらい経ちますか？",
        "q_documents": "今もお持ちの身分証明書や渡航書類はどれですか？",
        "q_languages": "どの言語を話せますか？",
        "q_destination": "ご家族やコミュニティがいる国、または保護を求めたい国はありますか？",
        "review_intro": "私はこう理解しました：",
        "review_confirm": "これで合っていますか？",
        "review_yes": "はい、正しいです",
        "review_no": "修正が必要です",
        "opt_yes": "はい", "opt_no": "いいえ",
        "opt_passport": "パスポート", "opt_id": "身分証明書", "opt_birth": "出生証明書",
        "opt_none": "なし", "opt_other": "その他",
        "ui_answer": "あなたの回答", "ui_continue": "続ける",
    },
    "Korean": {
        "welcome": "안녕하세요 — 도와드리겠습니다. 한 단계씩 진행할게요.",
        "q_current": "지금 어느 나라에 계신가요?",
        "q_origin": "원래 어느 나라 출신이신가요?",
        "q_reason": "{origin}에서 무슨 일이 있어 떠나게 되셨는지 말씀해 주시겠어요?",
        "q_danger": "지금 즉각적인 위험에 처해 계신가요?",
        "q_duration": "{origin}을(를) 떠난 지 얼마나 되셨나요?",
        "q_documents": "아직 가지고 계신 신분증이나 여행 서류는 무엇인가요?",
        "q_languages": "어떤 언어를 하실 수 있나요?",
        "q_destination": "가족이나 공동체가 있는 나라, 또는 보호를 받고 싶은 나라가 있나요?",
        "review_intro": "제가 이해한 내용입니다:",
        "review_confirm": "맞나요?",
        "review_yes": "네, 맞습니다",
        "review_no": "수정이 필요합니다",
        "opt_yes": "예", "opt_no": "아니요",
        "opt_passport": "여권", "opt_id": "신분증", "opt_birth": "출생증명서",
        "opt_none": "없음", "opt_other": "기타",
        "ui_answer": "당신의 답변", "ui_continue": "계속",
    },
    "Russian": {
        "welcome": "Здравствуйте — я здесь, чтобы помочь, мы будем идти шаг за шагом.",
        "q_current": "В какой стране вы сейчас находитесь?",
        "q_origin": "Из какой страны вы родом?",
        "q_reason": "Расскажите, что произошло в {origin}, из-за чего вам пришлось уехать?",
        "q_danger": "Находитесь ли вы прямо сейчас в непосредственной опасности?",
        "q_duration": "Как давно вы покинули {origin}?",
        "q_documents": "Какие документы, удостоверяющие личность, или проездные документы у вас остались?",
        "q_languages": "На каких языках вы говорите?",
        "q_destination": "Есть ли страна, где у вас есть семья или община, или куда вы предпочли бы обратиться за защитой?",
        "review_intro": "Вот что я понял:",
        "review_confirm": "Всё верно?",
        "review_yes": "Да, всё верно",
        "review_no": "Нужно кое-что изменить",
        "opt_yes": "Да", "opt_no": "Нет",
        "opt_passport": "Паспорт", "opt_id": "Удостоверение личности", "opt_birth": "Свидетельство о рождении",
        "opt_none": "Нет", "opt_other": "Другое",
        "ui_answer": "Ваш ответ", "ui_continue": "Продолжить",
    },
}


# Extra strings (still-in-country reason wording + the correction prompt),
# merged into TR. t() falls back to English for any language missing a key.
_EXTRA = {
    "English": {
        "q_reason_instill": "Can you tell me what is happening in {origin} that makes you fear for your safety?",
        "q_correct": "What would you like to correct? You can tell me in your own words.",
    },
    "French": {
        "q_reason_instill": "Pouvez-vous me dire ce qui se passe en {origin} qui vous fait craindre pour votre sécurité ?",
        "q_correct": "Que souhaitez-vous corriger ? Dites-le-moi avec vos propres mots.",
    },
    "Spanish": {
        "q_reason_instill": "¿Puedes contarme qué está pasando en {origin} que te hace temer por tu seguridad?",
        "q_correct": "¿Qué te gustaría corregir? Puedes decírmelo con tus propias palabras.",
    },
    "Portuguese": {
        "q_reason_instill": "Pode me contar o que está acontecendo em {origin} que faz você temer pela sua segurança?",
        "q_correct": "O que você gostaria de corrigir? Pode me dizer com suas próprias palavras.",
    },
    "Arabic": {
        "q_reason_instill": "هل يمكنك أن تخبرني بما يحدث في {origin} ويجعلك تخشى على سلامتك؟",
        "q_correct": "ما الذي تودّ تصحيحه؟ يمكنك إخباري بكلماتك الخاصة.",
    },
    "Hindi": {
        "q_reason_instill": "क्या आप बता सकते हैं कि {origin} में क्या हो रहा है जिससे आपको अपनी सुरक्षा का डर है?",
        "q_correct": "आप क्या ठीक करना चाहेंगे? आप अपने शब्दों में बता सकते हैं।",
    },
    "Chinese": {
        "q_reason_instill": "能告诉我{origin}正在发生什么、让您为自己的安全感到担忧吗？",
        "q_correct": "您想更正什么？可以用您自己的话告诉我。",
    },
    "Japanese": {
        "q_reason_instill": "{origin}で何が起きていて、ご自身の安全が脅かされていると感じるのか教えていただけますか？",
        "q_correct": "どこを修正したいですか？ ご自身の言葉で教えてください。",
    },
    "Korean": {
        "q_reason_instill": "{origin}에서 무슨 일이 일어나고 있어 안전이 걱정되시는지 말씀해 주시겠어요?",
        "q_correct": "무엇을 고치고 싶으신가요? 편하게 말씀해 주세요.",
    },
    "Russian": {
        "q_reason_instill": "Расскажите, что происходит в {origin}, из-за чего вы опасаетесь за свою безопасность?",
        "q_correct": "Что вы хотели бы исправить? Можете рассказать своими словами.",
    },
}
for _lang, _d in _EXTRA.items():
    TR.setdefault(_lang, {}).update(_d)


def t(language: str | None, sid: str) -> str:
    """Translation lookup with English fallback."""
    lang = language if language in TR else "English"
    return TR[lang].get(sid) or TR["English"].get(sid, sid)


def in_origin(session) -> bool:
    """True when the person is still in their country of origin."""
    o = (session.interview.origin_country or "").strip().lower()
    c = (session.interview.current_country or "").strip().lower()
    return bool(o) and o == c


def question_text(language: str | None, q: Question, session) -> str:
    """Localised question text, templated with collected values.

    Uses the alternate wording when the person is still in their origin country
    (so we don't ask "what made you leave" / "how long ago did you leave").
    """
    sid = q.alt_sid if (q.alt_sid and in_origin(session)) else q.sid
    raw = t(language, sid)
    origin = session.interview.origin_country or t(language, "q_origin")
    current = session.interview.current_country or ""
    return raw.replace("{origin}", str(origin)).replace("{current}", str(current))


def option_labels(language: str | None, q: Question) -> list[str]:
    if q.control == "yesno":
        return [t(language, "opt_yes"), t(language, "opt_no")]
    return [t(language, oid) for oid in q.options]


__all__ = ["Question", "QUESTIONS", "REVIEW_INDEX", "TR", "t", "question_text",
           "option_labels", "in_origin"]
