from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='/new_auction')],
        [KeyboardButton(text='/cancel_auction')],
        [KeyboardButton(text='/help')]
    ],
    resize_keyboard=True
)

def auction_kb(auction_id: int, current_price: int, step: int):
    new_bid = current_price + step
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f'Сделать ставку ({new_bid})', callback_data=f'bid_{auction_id}_{new_bid}')]
        ]
    )
