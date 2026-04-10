import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CANAL = "@promoscasaeconstrucao"

# ===================== ESTADOS =====================
AGUARDANDO_LINK, AGUARDANDO_CONFIRMACAO, AGUARDANDO_EDICAO = range(3)

oferta_temp = {}

logging.basicConfig(level=logging.INFO)

# ===================== BUSCAR DADOS DO PRODUTO =====================
def buscar_produto(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # Seguir redirecionamento do link curto
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(response.text, "html.parser")

        # Nome do produto
        nome = None
        tag_nome = soup.find("h1", class_=lambda c: c and "ui-pdp-title" in c)
        if tag_nome:
            nome = tag_nome.get_text(strip=True)

        # Preço atual
        preco = None
        tag_preco = soup.find("span", class_=lambda c: c and "andes-money-amount__fraction" in c)
        if tag_preco:
            preco = tag_preco.get_text(strip=True)

        # Preço original (antes do desconto)
        preco_original = None
        tag_original = soup.find("s", class_=lambda c: c and "andes-money-amount" in c)
        if tag_original:
            frac = tag_original.find("span", class_=lambda c: c and "andes-money-amount__fraction" in c)
            if frac:
                preco_original = frac.get_text(strip=True)

        return nome, preco, preco_original

    except Exception as e:
        logging.error(f"Erro ao buscar produto: {e}")
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

    nome, preco, preco_original = buscar_produto(url)

    if nome:
        oferta_temp["descricao"] = nome
    if preco:
        oferta_temp["preco"] = preco
    if preco_original:
        oferta_temp["preco_original"] = preco_original

    if not nome or not preco:
        await update.message.reply_text(
            "⚠️ Não consegui buscar os dados automaticamente.\n\n"
            "Digite no formato:\n`Nome do produto | Preço atual | Preço original`\n\n"
            "Exemplo: `Furadeira Bosch 700W | 149,90 | 299,90`\n"
            "_(Preço original é opcional — use só: `Furadeira Bosch 700W | 149,90`)_",
            parse_mode="Markdown"
        )
        return AGUARDANDO_EDICAO

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
            "✏️ Digite as informações no formato:\n`Nome do produto | Preço atual | Preço original`\n\n"
            "Exemplo: `Furadeira Bosch 700W | 149,90 | 299,90`",
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
