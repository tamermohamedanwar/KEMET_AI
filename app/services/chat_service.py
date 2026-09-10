from app import db
from app.models.chat import ChatMessage
from app.models.conversation import Conversation
from app.services.memory_service import MemoryService
from app.services.ai_service import ask_ai, parse_automation_response
from app.services.ai_usage_service import check_limit, record_usage
from app.models.user import User
from app.services.automation_service import automation_service
from app.rag.rag_service import rag_service


class ChatService:

    def generate_reply(
        self,
        message: str,
        user_id=None,
        conversation_id=None,
    ) -> tuple[str, int]:

        message = message.strip()

        if not message:
            return "من فضلك اكتب رسالة.", conversation_id

        if conversation_id is None:
            conversation = Conversation(
                user_id=user_id,
                title=message[:50] or "محادثة جديدة",
            )
            db.session.add(conversation)
            db.session.flush()
        else:
            conversation = Conversation.query.filter_by(id=conversation_id).first()

            if conversation and user_id and conversation.user_id != user_id:
                conversation = None

            if conversation is None:
                conversation = Conversation(
                    user_id=user_id,
                    title=message[:50] or "محادثة جديدة",
                )
                db.session.add(conversation)
                db.session.flush()

        history = ChatMessage.query.filter_by(
            conversation_id=conversation.id
        ).order_by(ChatMessage.id.desc()).limit(10).all()

        context = "\n".join(
            [
                f"المستخدم: {item.question}\nKemet AI: {item.answer}"
                for item in reversed(history)
            ]
        )

        memory_rules = [
            ("اسمي ", "name"),
            ("عملي ", "work"),
            ("أعمل في ", "work"),
            ("اهتماماتي ", "interests"),
            ("أنا أحب ", "interest"),
            ("أحب ", "interest"),
            ("لغتي المفضلة ", "language"),
        ]

        if "أنا " in message and "وأعمل في" in message:
            try:
                name = message.split("أنا ", 1)[1].split("وأعمل في", 1)[0].strip()
                work = message.split("وأعمل في", 1)[1].strip()
                if name:
                    MemoryService.save(user_id, "name", name)
                if work:
                    MemoryService.save(user_id, "work", work)
            except Exception:
                pass
        else:
            for prefix, key in memory_rules:
                if prefix in message:
                    value = message.split(prefix, 1)[1].strip()
                    if value:
                        MemoryService.save(user_id, key, value)
                    break

        if "ما اسمي" in message or "اسمى" in message or "اسمي ايه" in message:
            name = MemoryService.get(user_id, "name")
            if name:
                answer = f"اسمك {name}."
                self._save_message(conversation.id, user_id, message, answer)
                return answer, conversation.id

        if "ماذا تعرف عني" in message or "عرفني عن نفسي" in message:
            memories = MemoryService.all(user_id)
            if memories:
                labels = {
                    "name": "الاسم",
                    "work": "العمل",
                    "interests": "الاهتمامات",
                    "interest": "الاهتمام",
                    "language": "اللغة المفضلة"
                }
                info = "\n".join(
                    [f"- {labels.get(m.key, m.key)}: {m.value}" for m in memories]
                )
                answer = f"أعرف عنك:\n{info}"
            else:
                answer = "لسه مفيش معلومات محفوظة عنك."
            self._save_message(conversation.id, user_id, message, answer)
            return answer, conversation.id

        user = User.query.filter_by(id=user_id).first()

        organization_id = (
            user.organization_id
            if user and user.organization_id
            else None
        )

        rag_context = ""
        try:
            rag_context = rag_service.get_context(
                message,
                organization_id=organization_id,
            )
        except Exception:
            pass

        if rag_context:
            context += "\n\nمعلومات من الملفات المرفوعة:\n" + rag_context

        user = User.query.filter_by(id=user_id).first()

        if user and user.organization_id:
            usage = check_limit(user.organization_id)

            if not usage["allowed"]:
                answer = (
                    "تم الوصول إلى الحد الشهري لاستخدام الذكاء الاصطناعي "
                    "في خطتك الحالية."
                )
                self._save_message(
                    conversation.id,
                    user_id,
                    message,
                    answer
                )
                return answer, conversation.id

        raw_answer = ask_ai(
            message,
            context,
            organization_id=organization_id,
        )

        if user and user.organization_id:
            record_usage(
                user.organization_id,
                tokens=getattr(raw_answer, "tokens", 0),
            )

        automation_data = parse_automation_response(raw_answer)

        if automation_data and automation_data.get("action"):
            try:
                result = automation_service.execute(
                    automation_data.get("action"),
                    automation_data.get("parameters", {}),
                    user_id=user_id
                )

                if result.get("action") == "create_ticket":
                    answer = f"""✅ تم إنشاء تذكرة دعم بنجاح

رقم التذكرة: #{result.get("ticket_id")}
الحالة: مفتوحة"""
                else:
                    answer = str(result)

            except Exception as e:
                print("Automation Error:", e)
                answer = "حصلت مشكلة أثناء تنفيذ المهمة."
        else:
            answer = raw_answer

        self._save_message(conversation.id, user_id, message, answer)

        return answer, conversation.id

    def _save_message(self, conversation_id, user_id, question, answer):
        chat = ChatMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            question=question,
            answer=answer,
        )
        db.session.add(chat)
        db.session.commit()
