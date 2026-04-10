import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CANAL = "@promoscasaeconstrucao"

# ===================== ESTADOS =====================
AGUARDANDO_LINK, AGUARDANDO_DADOS, AGUARDANDO_CONFIRMACAO = range(3)

oferta_temp = {}
logging.basicConfig(level=logging.INFO)

# ===================== FORMATAR MENSAGEM =====================
def formatar_mensagem(oferta):
    descricao = oferta.get("descricao", "Produto")
    preco = oferta.get("preco", "")
    preco_original = oferta.get("preco_original")
    link = oferta.get("link", "")

    linhas = [f"🏠 *{descricao}*\n"]
    if preco_original:
        linhas.append(f"~~R$ {preco_original}~~")
    linhas.append(f"💥 *R$ {preco}*")
    linhas.append(f"\n🛒 [Comprar agora]({link})")
    linhas.append("\n📦 Frete grátis disponível!")
    linhas.append("⚡️ Aproveite enquanto dura!")

    return "\n".join(linhas)

# ===================== HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👷 Olá! Bem-vindo ao bot de ofertas.\n\n"
        "Use /novaoferta para postar um produto no canal.\n"
        "Use /cancelar para cancelar a qualquer momento."
    )

async def nova_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp.clear()
    await update.message.reply_text(
        "🔗 Me manda o *link do produto* (seu link de afiliado):",
        parse_mode="Markdown"
    )
    return AGUARDANDO_LINK

async def receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp["link"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Agora me manda os dados no formato:\n\n"
        "`Nome do produto | Preço atual | Preço original`\n\n"
        "Exemplo: `Furadeira Bosch 700W | 149,90 | 299,90`\n\n"
        "_(O preço original é opcional — use só: `Furadeira Bosch 700W | 149,90`)_",
        parse_mode="Markdown"
    )
    return AGUARDANDO_DADOS

async def receber_dados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    partes = [p.strip() for p in texto.split("|")]

    if len(partes) < 2:
        await update.message.reply_text(
            "⚠️ Formato inválido. Use:\n`Nome | Preço atual | Preço original`",
            parse_mode="Markdown"
        )
        return AGUARDANDO_DADOS

    oferta_temp["descricao"] = partes[0]
    oferta_temp["preco"] = partes[1]
    oferta_temp["preco_original"] = partes[2] if len(partes) > 2 else None

    preview = formatar_mensagem(oferta_temp)
    keyboard = [
        [InlineKeyboardButton("✅ Postar no canal", callback_data="confirmar")],
        [InlineKeyboardButton("✏️ Corrigir dados", callback_data="editar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ]
    await update.message.reply_text(
        f"📋 *Preview da oferta:*\n\n{preview}\n\n_Deseja postar no canal?_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=False
    )
    return AGUARDANDO_CONFIRMACAO

async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirmar":
        mensagem = formatar_mensagem(oferta_temp)
        await context.bot.send_message(
            chat_id=CANAL,
            text=mensagem,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        await query.edit_message_text("✅ Oferta postada no canal com sucesso!")
        oferta_temp.clear()
        return ConversationHandler.END

    elif query.data == "editar":
        await query.edit_message_text(
            "✏️ Me manda os dados corrigidos:\n\n"
            "`Nome do produto | Preço atual | Preço original`",
            parse_mode="Markdown"
        )
        return AGUARDANDO_DADOS

    else:
        await query.edit_message_text("❌ Oferta cancelada.")
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
