import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CANAL = "@promonotebookarq"

AGUARDANDO_LINK, AGUARDANDO_DADOS, AGUARDANDO_CONFIRMACAO = range(3)
oferta_temp = {}
logging.basicConfig(level=logging.INFO)

# ===================== FORMATAR MENSAGEM =====================
def formatar_mensagem(oferta):
    linhas = [f"💻 *{oferta['descricao']}*\n"]
    if oferta.get("preco_original") and oferta.get("desconto"):
        linhas.append(f"~~R$ {oferta['preco_original']}~~")
        linhas.append(f"💥 *R$ {oferta['preco']}* — *{oferta['desconto']}% OFF*")
    else:
        linhas.append(f"💥 *R$ {oferta['preco']}*")
    linhas.append(f"\n🛒 [Comprar agora]({oferta['link']})")
    linhas.append("\n📦 Frete grátis disponível!")
    linhas.append("⚡️ Aproveite enquanto dura!")
    return "\n".join(linhas)

# ===================== HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💻 Olá! Sou o bot de ofertas de notebooks e periféricos.\n\n"
        "/novaoferta — postar uma oferta no canal\n"
        "/cancelar — cancelar operação"
    )

async def nova_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp.clear()
    await update.message.reply_text("🔗 Me manda o *link do produto*:", parse_mode="Markdown")
    return AGUARDANDO_LINK

async def receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp["link"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Me manda os dados:\n\n"
        "`Nome | Preço atual | Preço original`\n\n"
        "Exemplo: `Notebook Dell i5 8GB | 2.499,00 | 3.199,00`\n"
        "_(Preço original é opcional)_",
        parse_mode="Markdown"
    )
    return AGUARDANDO_DADOS

async def receber_dados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partes = [p.strip() for p in update.message.text.strip().split("|")]
    if len(partes) < 2:
        await update.message.reply_text("⚠️ Use: `Nome | Preço | Preço original`", parse_mode="Markdown")
        return AGUARDANDO_DADOS

    oferta_temp["descricao"] = partes[0]
    oferta_temp["preco"] = partes[1]

    if len(partes) > 2:
        try:
            p_atual = float(partes[1].replace(",", "."))
            p_original = float(partes[2].replace(",", "."))
            oferta_temp["preco_original"] = partes[2]
            oferta_temp["desconto"] = int(((p_original - p_atual) / p_original) * 100) if p_original > p_atual else 0
        except:
            oferta_temp["preco_original"] = partes[2]
            oferta_temp["desconto"] = 0
    else:
        oferta_temp["preco_original"] = None
        oferta_temp["desconto"] = 0

    preview = formatar_mensagem(oferta_temp)
    keyboard = [
        [InlineKeyboardButton("✅ Postar no canal", callback_data="confirmar")],
        [InlineKeyboardButton("✏️ Corrigir dados", callback_data="editar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ]
    await update.message.reply_text(
        f"📋 *Preview:*\n\n{preview}\n\n_Deseja postar?_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AGUARDANDO_CONFIRMACAO

async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirmar":
        await context.bot.send_message(
            chat_id=CANAL,
            text=formatar_mensagem(oferta_temp),
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        await query.edit_message_text("✅ Oferta postada com sucesso!")
        oferta_temp.clear()
        return ConversationHandler.END
    elif query.data == "editar":
        await query.edit_message_text("✏️ Me manda os dados corrigidos:\n`Nome | Preço | Preço original`", parse_mode="Markdown")
        return AGUARDANDO_DADOS
    else:
        await query.edit_message_text("❌ Cancelado.")
        oferta_temp.clear()
        return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp.clear()
    await update.message.reply_text("❌ Operação cancelada.")
    return ConversationHandler.END

# ===================== MAIN =====================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("novaoferta", nova_oferta)],
        states={
            AGUARDANDO_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_link)],
            AGUARDANDO_DADOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_dados)],
            AGUARDANDO_CONFIRMACAO: [CallbackQueryHandler(confirmar)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("🤖 Bot rodando...")
    app.run_polling()
