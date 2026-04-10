import os
import logging
import requests
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler, Application

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")
CANAL = "@promoscasaeconstrucao"
DESCONTO_MINIMO = 10  # percentual mínimo
OFERTAS_POR_CICLO = 3  # postadas por vez (4 ciclos/dia = ~12 por dia)

# Categorias no ML Brasil
CATEGORIAS = {
    "Ferramentas":              "MLB1574",
    "Hidráulica e Encanamento": "MLB1586",
    "Iluminação":               "MLB1576",
    "Tintas e Acabamentos":     "MLB1590",
    "Móveis":                   "MLB1575",
    "Eletrodomésticos":         "MLB1574",
}

produtos_postados = set()
logging.basicConfig(level=logging.INFO)

# ===================== API ML =====================
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
        return response.json().get("access_token")
    except Exception as e:
        logging.error(f"Erro token ML: {e}")
        return None

def buscar_ofertas():
    token = get_ml_token()
    if not token:
        logging.error("Sem token ML")
        return []

    headers = {"Authorization": f"Bearer {token}"}
    ofertas = []

    for categoria_nome, categoria_id in CATEGORIAS.items():
        try:
            response = requests.get(
                "https://api.mercadolibre.com/sites/MLB/search",
                headers=headers,
                params={
                    "category": categoria_id,
                    "sort": "price_asc",
                    "limit": 20,
                    "condition": "new",
                },
                timeout=10
            )
            items = response.json().get("results", [])

            for item in items:
                item_id = item.get("id")
                if item_id in produtos_postados:
                    continue

                preco = item.get("price", 0)
                preco_original = item.get("original_price")
                titulo = item.get("title", "")
                link = item.get("permalink", "")

                if not preco_original or preco_original <= preco:
                    continue

                desconto = ((preco_original - preco) / preco_original) * 100
                if desconto < DESCONTO_MINIMO:
                    continue

                ofertas.append({
                    "id": item_id,
                    "descricao": titulo,
                    "preco": f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "preco_original": f"{preco_original:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "link": link,
                    "desconto": int(desconto),
                    "categoria": categoria_nome,
                })

        except Exception as e:
            logging.error(f"Erro ao buscar categoria {categoria_nome}: {e}")

    # Ordenar por maior desconto
    ofertas.sort(key=lambda x: x["desconto"], reverse=True)
    return ofertas

# ===================== FORMATAR MENSAGEM =====================
def formatar_mensagem(oferta):
    linhas = [
        f"🏠 *{oferta['descricao']}*\n",
        f"🏷️ Categoria: {oferta['categoria']}",
        f"~~R$ {oferta['preco_original']}~~",
        f"💥 *R$ {oferta['preco']}* — *{oferta['desconto']}% OFF*",
        f"\n🛒 [Comprar agora]({oferta['link']})",
        "\n📦 Frete grátis disponível!",
        "⚡️ Aproveite enquanto dura!"
    ]
    return "\n".join(linhas)

# ===================== JOB: POSTAR AUTOMATICAMENTE =====================
async def postar_ofertas_automatico(context):
    logging.info("Buscando ofertas automáticas...")
    ofertas = buscar_ofertas()

    if not ofertas:
        logging.info("Nenhuma oferta encontrada.")
        return

    postadas = 0
    for oferta in ofertas:
        if postadas >= OFERTAS_POR_CICLO:
            break
        if oferta["id"] in produtos_postados:
            continue
        try:
            mensagem = formatar_mensagem(oferta)
            await context.bot.send_message(
                chat_id=CANAL,
                text=mensagem,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            produtos_postados.add(oferta["id"])
            postadas += 1
            logging.info(f"Postado: {oferta['descricao']}")
        except Exception as e:
            logging.error(f"Erro ao postar: {e}")

    logging.info(f"{postadas} ofertas postadas.")

# ===================== HANDLERS MANUAIS =====================
AGUARDANDO_LINK, AGUARDANDO_DADOS, AGUARDANDO_CONFIRMACAO = range(3)
oferta_temp = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👷 Olá! Sou o bot de ofertas.\n\n"
        "🤖 Posto ofertas automaticamente ao longo do dia.\n\n"
        "Você também pode postar manualmente:\n"
        "/novaoferta — postar um produto\n"
        "/forcarbusca — buscar ofertas agora\n"
        "/cancelar — cancelar operação"
    )

async def forcar_busca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Buscando ofertas agora, aguarde...")
    await postar_ofertas_automatico(context)
    await update.message.reply_text("✅ Busca concluída!")

async def nova_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp.clear()
    await update.message.reply_text("🔗 Me manda o *link do produto*:", parse_mode="Markdown")
    return AGUARDANDO_LINK

async def receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp["link"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Me manda os dados:\n\n"
        "`Nome | Preço atual | Preço original`\n\n"
        "Exemplo: `Furadeira Bosch 700W | 149,90 | 299,90`\n"
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
    oferta_temp["preco_original"] = partes[2] if len(partes) > 2 else None
    oferta_temp["desconto"] = None
    oferta_temp["categoria"] = "Casa e Construção"

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

    # Agendamento: 4 vezes ao dia (horário UTC -3 = BRT)
    # 8h, 12h, 17h, 20h BRT = 11h, 15h, 20h, 23h UTC
    job_queue = app.job_queue
    job_queue.run_daily(postar_ofertas_automatico, time=time(11, 0))
    job_queue.run_daily(postar_ofertas_automatico, time=time(15, 0))
    job_queue.run_daily(postar_ofertas_automatico, time=time(20, 0))
    job_queue.run_daily(postar_ofertas_automatico, time=time(23, 0))

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
    app.add_handler(CommandHandler("forcarbusca", forcar_busca))
    app.add_handler(conv_handler)

    print("🤖 Bot rodando com postagem automática...")
    app.run_polling()
