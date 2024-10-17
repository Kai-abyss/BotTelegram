import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from telegram.error import RetryAfter, TimedOut

# Thông tin Bot và Admin
TOKEN = 'YOUR TOKEN'
ADMIN_ID = 'YOUR ID'
BANK_ACCOUNT = "0123456789 - Ngân hàng ABC"

# Danh sách sản phẩm giả lập
products = {
    1: {"name": "Sản phẩm A", "price": 100000, "image": "https://i.example.com/1234.jpg"},
    2: {"name": "Sản phẩm B", "price": 150000, "image": "https://i.example.it/1234.jpeg"},
    3: {"name": "Sản phẩm C", "price": 200000, "image": "https://i.example.it/1234.jpeg"},
}

# Thiết lập logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Trạng thái cho ConversationHandler
AWAITING_PAYMENT, AWAITING_USER_INFO = range(2)

# Hàm bắt đầu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Chào mừng! Sử dụng /products để xem danh sách sản phẩm.')

# Hàm help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Sử dụng /products để xem danh sách sản phẩm. Nếu bạn gặp vấn đề, hãy liên hệ admin.')

# Hàm hiển thị danh sách sản phẩm với hình ảnh
async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for product_id, product in products.items():
        keyboard = [[InlineKeyboardButton(f"Mua {product['name']} - {product['price']}đ", callback_data=f"buy_{product_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Gửi hình ảnh của sản phẩm cùng với nút
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=product['image'],
            caption=f"{product['name']} - {product['price']}đ",
            reply_markup=reply_markup
        )

# Hàm xử lý khi người dùng muốn mua sản phẩm
async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split('_')[1])
    product = products.get(product_id)
    
    if product:
        context.user_data['selected_product'] = product
        context.user_data['user_id'] = query.from_user.id
        
        keyboard = [[InlineKeyboardButton("Xác nhận", callback_data=f"confirm_{query.from_user.id}_{product['name']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_photo(
            photo=product['image'],
            caption=f"{product['name']} - {product['price']}đ\n\nThông tin thanh toán: {BANK_ACCOUNT}\n\nVui lòng thanh toán và nhấn 'Xác nhận'.",
            reply_markup=reply_markup
        )

        await send_message_with_retry(context.bot, ADMIN_ID,
            f"Có đơn hàng mới!\nNgười dùng: {query.from_user.first_name} (ID: {query.from_user.id})\nSản phẩm: {product['name']}\nGiá: {product['price']}đ\nThông tin thanh toán: {BANK_ACCOUNT}"
        )
        return AWAITING_PAYMENT
    else:
        await query.message.reply_text("Sản phẩm không tồn tại!")
        return ConversationHandler.END

# Hàm xử lý xác nhận thanh toán từ admin và yêu cầu người dùng nhập thông tin
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, user_id, product_name = query.data.split('_')
    user_id = int(user_id)
    
    await send_message_with_retry(context.bot, user_id,
        f"Thanh toán của bạn cho {product_name} đã được xác nhận. Vui lòng nhập thông tin chi tiết (ví dụ: địa chỉ nhận hàng)."
    )
    return AWAITING_USER_INFO

# Hàm xử lý thông tin người dùng nhập vào
async def process_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = update.message.text
    context.user_data['user_info'] = user_info
    
    product = context.user_data.get('selected_product')
    if product:
        admin_message = f"Đơn hàng đã được xác nhận:\nSản phẩm: {product['name']}\nGiá: {product['price']}đ\nThông tin khách hàng: {user_info}"
        await send_message_with_retry(context.bot, ADMIN_ID, admin_message)
    
    await update.message.reply_text("Cảm ơn bạn đã mua hàng! Chúng tôi sẽ xử lý đơn hàng của bạn sớm nhất có thể.")
    
    # Thêm phần xử lý khi admin xác nhận đơn hàng thành công hoặc không thể xác nhận
    keyboard = [
        [InlineKeyboardButton("Xác nhận đã xử lý đơn hàng", callback_data=f"processed_{context.user_data['user_id']}")],
        [InlineKeyboardButton("Không thể xác nhận đơn hàng", callback_data=f"unprocessed_{context.user_data['user_id']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_message_with_retry(context.bot, ADMIN_ID, "Nhấn nút dưới đây để xác nhận hoặc từ chối đơn hàng:", reply_markup=reply_markup)
    
    return ConversationHandler.END

# Hàm xử lý khi admin xác nhận đơn hàng đã được xử lý thành công
async def process_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[1])
    
    # Gửi tin nhắn thông báo cho khách hàng
    await send_message_with_retry(context.bot, user_id,
        "Đơn hàng của bạn đã được xử lý thành công. Vui lòng kiểm tra email của bạn để biết thêm chi tiết."
    )
    await query.message.reply_text("Đã xác nhận đơn hàng thành công.")
    
    return ConversationHandler.END

# Hàm xử lý khi admin không thể xác nhận đơn hàng
async def unprocess_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split('_')[1])

    # Gửi tin nhắn thông báo cho khách hàng
    await send_message_with_retry(context.bot, user_id,
        "Đơn hàng của bạn không thể được xác nhận vào lúc này. Vui lòng liên hệ với bộ phận hỗ trợ để biết thêm chi tiết."
    )
    await query.message.reply_text("Đã thông báo khách hàng về việc không thể xác nhận đơn hàng.")

    return ConversationHandler.END

# Hàm hủy conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Đã hủy thao tác.')
    return ConversationHandler.END

# Hàm gửi tin nhắn với cơ chế retry (cập nhật để hỗ trợ thêm các tham số tùy chọn như reply_markup)
async def send_message_with_retry(bot, chat_id, text, max_retries=3, retry_delay=1, **kwargs):
    for attempt in range(max_retries):
        try:
            return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except (RetryAfter, TimedOut) as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(retry_delay * (attempt + 1))

async def post_init(application: Application) -> None:
    await application.bot.delete_webhook()

# Main function
def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_product, pattern='^buy_')],
        states={
            AWAITING_PAYMENT: [CallbackQueryHandler(confirm_payment, pattern='^confirm_')],
            AWAITING_USER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_info)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(conv_handler)
    
    # Thêm handler cho việc xử lý đơn hàng thành công hoặc không thể xác nhận
    application.add_handler(CallbackQueryHandler(process_order, pattern='^processed_'))
    application.add_handler(CallbackQueryHandler(unprocess_order, pattern='^unprocessed_'))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
