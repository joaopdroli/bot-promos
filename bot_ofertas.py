import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CANAL = "@promonotebookarq"

# ===================== ESTADOS =====================
(AGUARDANDO_LINK, AGUARDANDO_DADOS, AGUARDANDO_CATEGORIA,
 AGUARDANDO_CUPOM, AGUARDANDO_CONFIRMACAO) = range(5)

oferta_temp = {}
logging.basicConfig(level=logging.INFO)

# ===================== CATEGORIAS =====================
CATEGORIAS = [
    "💻 Notebook", "🖱️ Mouse", "⌨️ Teclado",
    "🖱️⌨️ Kit Teclado e Mouse", "💾 SSD", "🧠 RAM",
    "🖱️ Mousepad", "🔧 Suporte", "🔌 Hub USB", "🖥️ Monitor"
]

EMOJI_CATEGORIA = {
    "💻 Notebook": "💻",
    "🖱️ Mouse": "🖱️",
    "⌨️ Teclado": "⌨️",
    "🖱️⌨️ Kit Teclado e Mouse": "🖱️⌨️",
    "💾 SSD": "💾",
    "🧠 RAM": "🧠",
    "🖱️ Mousepad": "🖱️",
    "🔧 Suporte": "🔧",
    "🔌 Hub USB": "🔌",
    "🖥️ Monitor": "🖥️",
}

# ===================== BUSCAR AVALIAÇÃO ML =====================
def buscar_avaliacao(link):
    try:
        import re
        match = re.search(r'MLB-?(\d+)', link)
        if not match:
            return None, None
        item_id = f"MLB{match.group(1)}"
        response = requests.get(
            f"https://api.mercadolibre.com/reviews/item/{item_id}",
            timeout=8
        )
        data = response.json()
        rating = data.get("rating_average")
        total = data.get("paging", {}).get("total")
        if rating and total:
            return round(rating, 1), total
        return None, None
    except Exception as e:
        logging.error(f"Erro ao buscar avaliação: {e}")
        return None, None

# ===================== FORMATAR MENSAGEM =====================
def formatar_mensagem(oferta):
    emoji = EMOJI_CATEGORIA.get(oferta.get("categoria", ""), "🛍️")
    linhas = [f"{emoji} *{oferta['descricao']}*\n"]

    if oferta.get("categoria"):
        linhas.append(f"🏷️ _{oferta['categoria']}_")

    if oferta.get("avaliacao"):
        estrelas = round(oferta["avaliacao"])
        linhas.append(f"{'⭐' * estrelas} {oferta['avaliacao']} — {oferta.get('total_avaliacoes', '')} avaliações\n")

    if oferta.get("preco_original") and oferta.get("desconto"):
        linhas.append(f"~~R$ {oferta['preco_original']}~~")
        linhas.append(f"💥 *R$ {oferta['preco']}* — *{oferta['desconto']}% OFF*")
    else:
        linhas.append(f"💥 *R$ {oferta['preco']}*")

    if oferta.get("cupom"):
        linhas.append(f"\n🎟️ Cupom: `{oferta['cupom']}`")

    linhas.append(f"\n🛒 [Comprar agora]({oferta['link']})")
    linhas.append("\n📦 Frete grátis disponível!")
    linhas.append("⚡️ Aproveite enquanto dura!")
    return "\n".join(linhas)

# ===================== TECLADO CATEGORIAS =====================
def teclado_categorias():
    keyboard = []
    row = []
    for i, cat in enumerate(CATEGORIAS):
        row.append(InlineKeyboardButton(cat, callback_data=f"cat_{i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

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
        "`Nome / Preço atual / Preço original`\n\n"
        "Exemplo: `Notebook Dell i5 8GB / 2.499,00 / 3.199,00`\n"
        "_(Preço original é opcional)_",
        parse_mode="Markdown"
    )
    return AGUARDANDO_DADOS

async def receber_dados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partes = [p.strip() for p in update.message.text.strip().split("/")]
    if len(partes) < 2:
        await update.message.reply_text("⚠️ Use: `Nome / Preço / Preço original`", parse_mode="Markdown")
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

    # Buscar avaliação
    avaliacao, total = buscar_avaliacao(oferta_temp["link"])
    oferta_temp["avaliacao"] = avaliacao
    oferta_temp["total_avaliacoes"] = total

    await update.message.reply_text(
        "📦 Selecione a *categoria* do produto:",
        parse_mode="Markdown",
        reply_markup=teclado_categorias()
    )
    return AGUARDANDO_CATEGORIA

async def receber_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.replace("cat_", ""))
    oferta_temp["categoria"] = CATEGORIAS[idx]

    await query.edit_message_text(
        "🎟️ Tem cupom de desconto?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎟️ Adicionar cupom", callback_data="add_cupom")],
            [InlineKeyboardButton("⏭️ Pular", callback_data="skip_cupom")],
        ])
    )
    return AGUARDANDO_CUPOM

async def opcao_cupom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add_cupom":
        await query.edit_message_text("🎟️ Digite o código do cupom:")
        return AGUARDANDO_CUPOM
    else:
        oferta_temp["cupom"] = None
        preview = formatar_mensagem(oferta_temp)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Postar no canal", callback_data="confirmar")],
            [InlineKeyboardButton("✏️ Corrigir dados", callback_data="editar")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
        ])
        await query.edit_message_text(
            f"📋 *Preview:*\n\n{preview}\n\n_Deseja postar?_",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return AGUARDANDO_CONFIRMACAO

async def receber_cupom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp["cupom"] = update.message.text.strip().upper()
    preview = formatar_mensagem(oferta_temp)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Postar no canal", callback_data="confirmar")],
        [InlineKeyboardButton("✏️ Corrigir dados", callback_data="editar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ])
    await update.message.reply_text(
        f"📋 *Preview:*\n\n{preview}\n\n_Deseja postar?_",
        parse_mode="Markdown",
        reply_markup=keyboard
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
        await query.edit_message_text("✏️ Me manda os dados corrigidos:\n`Nome / Preço / Preço original`", parse_mode="Markdown")
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
            AGUARDANDO_CATEGORIA: [CallbackQueryHandler(receber_categoria, pattern="^cat_")],
            AGUARDANDO_CUPOM: [
                CallbackQueryHandler(opcao_cupom, pattern="^(add_cupom|skip_cupom)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_cupom),
            ],
            AGUARDANDO_CONFIRMACAO: [CallbackQueryHandler(confirmar)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("🤖 Bot rodando...")
    app.run_polling()
