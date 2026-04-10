import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")
CANAL = "@promoscasaeconstrucao"

# ===================== ESTADOS =====================
AGUARDANDO_LINK, AGUARDANDO_CONFIRMACAO, AGUARDANDO_EDICAO = range(3)

oferta_temp = {}
logging.basicConfig(level=logging.INFO)

# ===================== API MERCADO LIVRE =====================
def get_ml_token():
    try:
        response = requests.post(
            "https://api.mercadolibre.com/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": ML_CLIENT_ID,
                "client_secret": ML_CLIENT_SECRET,
            },
            timeout=10
        )
        data = response.json()
        return data.get("access_token")
    except Exception as e:
        logging.error(f"Erro ao obter token ML: {e}")
        return None

def extrair_item_id(url):
    try:
        # Seguir redirecionamento para pegar URL final
        response = requests.get(url, timeout=10, allow_redirects=True)
        final_url = response.url
        # Extrair ID do produto (ex: MLB123456789)
        import re
        match = re.search(r'MLB-?(\d+)', final_url)
        if match:
            return f"MLB{match.group(1)}"
        return None
    except Exception as e:
        logging.error(f"Erro ao extrair item ID: {e}")
        return None

def buscar_produto_ml(url):
    try:
        token = get_ml_token()
        if not token:
            return None, None, None

        item_id = extrair_item_id(url)
        if not item_id:
            return None, None, None

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"https://api.mercadolibre.com/items/{item_id}",
            headers=headers,
            timeout=10
        )
        data = response.json()

        nome = data.get("title")
        preco = data.get("price")
        preco_original = data.get("original_price")

        if preco:
            preco = f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if preco_original:
            preco_original = f"{preco_original:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        return nome, preco, preco_original

    except Exception as e:
        logging.error(f"Erro ao buscar produto ML: {e}")
        return None, None, None

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
    await update.message.reply_text("🔗 Me manda o *link do produto* (seu link de afiliado):", parse_mode="Markdown")
    return AGUARDANDO_LINK

async def receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    oferta_temp["link"] = url

    await update.message.reply_text("🔍 Buscando informações do produto, aguarde...")

    nome, preco, preco_original = buscar_produto_ml(url)

    if nome and preco:
        oferta_temp["descricao"] = nome
        oferta_temp["preco"] = preco
        oferta_temp["preco_original"] = preco_original

        preview = formatar_mensagem(oferta_temp)
        keyboard = [
            [InlineKeyboardButton("✅ Postar assim", callback_data="confirmar")],
            [InlineKeyboardButton("✏️ Editar informações", callback_data="editar")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
        ]
        await update.message.reply_text(
            f"📋 *Preview da oferta:*\n\n{preview}\n\n_Deseja postar no canal?_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=False
        )
        return AGUARDANDO_CONFIRMACAO
    else:
        await update.message.reply_text(
            "⚠️ Não consegui buscar os dados automaticamente.\n\n"
            "Digite no formato:\n`Nome do produto | Preço atual | Preço original`\n\n"
            "Exemplo: `Furadeira Bosch 700W | 149,90 | 299,90`\n"
            "_(Preço original é opcional)_",
            parse_mode="Markdown"
        )
        return AGUARDANDO_EDICAO

async def receber_edicao_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    partes = [p.strip() for p in texto.split("|")]

    if len(partes) < 2:
        await update.message.reply_text("⚠️ Formato inválido. Use: `Nome | Preço atual | Preço original`", parse_mode="Markdown")
        return AGUARDANDO_EDICAO

    oferta_temp["descricao"] = partes[0]
    oferta_temp["preco"] = partes[1]
    oferta_temp["preco_original"] = partes[2] if len(partes) > 2 else None

    preview = formatar_mensagem(oferta_temp)
    keyboard = [
        [InlineKeyboardButton("✅ Postar assim", callback_data="confirmar")],
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
            "✏️ Digite as informações no formato:\n`Nome do produto | Preço atual | Preço original`",
            parse_mode="Markdown"
        )
        return AGUARDANDO_EDICAO
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
            AGUARDANDO_CONFIRMACAO: [CallbackQueryHandler(confirmar)],
            AGUARDANDO_EDICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_edicao_manual)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("🤖 Bot rodando...")
    app.run_polling()
