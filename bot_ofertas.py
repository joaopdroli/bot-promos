import os
import logging
import requests
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")
CANAL = "@promoscasaeconstrucao"
OFERTAS_POR_CICLO = 3

CATEGORIAS = {
    "Ferramentas e Construção": "MLB263532",
    "Casa, Móveis e Decoração":  "MLB1574",
    "Eletrodomésticos":          "MLB5726",
    "Construção":                "MLB1500",
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
        return []

    headers = {"Authorization": f"Bearer {token}"}
    ofertas = []

    for categoria_nome, categoria_id in CATEGORIAS.items():
        try:
            # Busca com filtro de promoção ativa
            response = requests.get(
                "https://api.mercadolibre.com/sites/MLB/search",
                headers=headers,
                params={
                    "category": categoria_id,
                    "sort": "relevance",
                    "limit": 50,
                    "condition": "new",
                    "promotions": "discount_price",
                },
                timeout=10
            )
            data = response.json()
            items = data.get("results", [])
            logging.info(f"{categoria_nome}: {len(items)} itens")

            for item in items:
                item_id = item.get("id")
                if item_id in produtos_postados:
                    continue

                preco = item.get("price", 0)
                preco_original = item.get("original_price") or item.get("prices", {})
                titulo = item.get("title", "")
                link = item.get("permalink", "")

                # Tenta pegar desconto de diferentes campos
                desconto = 0
                if isinstance(preco_original, (int, float)) and preco_original > preco:
                    desconto = int(((preco_original - preco) / preco_original) * 100)
                    preco_original_str = f"{preco_original:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                else:
                    preco_original = None
                    preco_original_str = None

                ofertas.append({
                    "id": item_id,
                    "descricao": titulo,
                    "preco": f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "preco_original": preco_original_str,
                    "link": link,
                    "desconto": desconto,
                    "categoria": categoria_nome,
                })

        except Exception as e:
            logging.error(f"Erro {categoria_nome}: {e}")

    # Prioriza os com desconto, depois os sem
    ofertas.sort(key=lambda x: x["desconto"], reverse=True)
    logging.info(f"Total ofertas: {len(ofertas)}")
    return ofertas

# ===================== FORMATAR MENSAGEM =====================
def formatar_mensagem(oferta):
    linhas = [f"🏠 *{oferta['descricao']}*\n"]
    if oferta.get("categoria"):
        linhas.append(f"🏷️ _{oferta['categoria']}_")
    if oferta.get("preco_original"):
        linhas.append(f"~~R$ {oferta['preco_original']}~~")
        linhas.append(f"💥 *R$ {oferta['preco']}* — *{oferta['desconto']}% OFF*")
    else:
        linhas.append(f"💥 *R$ {oferta['preco']}*")
    linhas.append(f"\n🛒 [Comprar agora]({oferta['link']})")
    linhas.append("\n📦 Frete grátis disponível!")
    linhas.append("⚡️ Aproveite enquanto dura!")
    return "\n".join(linhas)

# ===================== JOB AUTOMÁTICO =====================
async def postar_ofertas_automatico(context):
    logging.info("Buscando ofertas...")
    ofertas = buscar_ofertas()

    if not ofertas:
        logging.info("Nenhuma oferta.")
        return

    postadas = 0
    for oferta in ofertas:
        if postadas >= OFERTAS_POR_CICLO:
            break
        if oferta["id"] in produtos_postados:
            continue
        try:
            await context.bot.send_message(
                chat_id=CANAL,
                text=formatar_mensagem(oferta),
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            produtos_postados.add(oferta["id"])
            postadas += 1
        except Exception as e:
            logging.error(f"Erro ao postar: {e}")

    logging.info(f"{postadas} ofertas postadas.")

# ===================== HANDLERS MANUAIS =====================
AGUARDANDO_LINK, AGUARDANDO_DADOS, AGUARDANDO_CONFIRMACAO = range(3)
oferta_temp = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👷 Olá! Sou o bot de ofertas.\n\n"
        "🤖 Posto automaticamente às 8h, 12h, 17h e 20h.\n\n"
        "/novaoferta — postar manualmente\n"
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
    oferta_temp["categoria"] = None
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

    print("🤖 Bot rodando...")
    app.run_polling()
