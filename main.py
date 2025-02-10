import asyncio
import os
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv

from db import Database
from keyboards import admin_kb, auction_kb

load_dotenv()

bot_token = os.getenv("TOKEN")
channel_id = os.getenv("CHANNEL_ID")

if not bot_token:
    print("Error: TOKEN environment variable not set.")
    exit()

if not channel_id:
    print("Error: CHANNEL_ID environment variable not set.")
    exit()

bot = Bot(token=bot_token)
db = Database(
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME")
)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.check_user(message.from_user.id)
    if not user:
        await db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        await message.answer("Добро пожаловать! Вы добавлены в базу данных.", reply_markup=admin_kb)
    else:
        await message.answer("С возвращением!", reply_markup=admin_kb)

@router.message(Command(commands="new_auction"))
async def cmd_new_auction(message: Message):
    await message.answer("Введите название лота:")
    await bot.set_state(message.from_user.id, {})  # Инициализируем состояние

    @router.message(lambda msg: msg.from_user.id == message.from_user.id, state=None)
    async def process_auction_data(message: types.Message, state: dict):
        if not state.get("title"):
            state["title"] = message.text
            await message.answer("Введите описание лота:")
        elif not state.get("description"):
            state["description"] = message.text
            await message.answer("Введите начальную цену:")
        elif not state.get("start_price"):
            try:
                state["start_price"] = int(message.text)
                await message.answer("Введите шаг ставки:")
            except ValueError:
                await message.answer("Некорректное значение начальной цены. Введите число.")
        elif not state.get("bid_step"):
            try:
                state["bid_step"] = int(message.text)
                await message.answer("Введите продолжительность аукциона в минутах:")
            except ValueError:
                await message.answer("Некорректное значение шага ставки. Введите число.")
        elif not state.get("end_time_minutes"):
            try:
                state["end_time_minutes"] = int(message.text)
                auction_id = await db.create_auction(
                    admin_id=message.from_user.id,
                    title=state["title"],
                    description=state["description"],
                    starting_bid=state["start_price"],
                    bid_step=state["bid_step"],
                    end_time_minutes=state["end_time_minutes"]
                )
                if auction_id:
                    await message.answer(f"Аукцион создан! ID: {auction_id}", reply_markup=auction_kb(auction_id, state["start_price"], state["bid_step"]))
                    await bot.delete_state(message.from_user.id)  # Очищаем состояние
                else:
                    await message.answer("Ошибка создания аукциона. Попробуйте еще раз.")
            except ValueError:
                await message.answer("Некорректное значение продолжительности аукциона. Введите число.")

@router.callback_query(F.data.startswith("bid_"))
async def process_bid(call: CallbackQuery):
    try:
        _, auction_id, new_bid = call.data.split("_")
        auction_id, new_bid = int(auction_id), int(new_bid)

        auction = await db.get_auction(auction_id)
        if not auction:
            await call.answer("Аукцион не найден!", show_alert=True)
            return

        if not await db.place_bid(auction_id, call.from_user.id, new_bid):
            await call.answer("Ставка слишком низкая или уже завершена!", show_alert=True)
            return

        user = await db.check_user(call.from_user.id)
        await call.message.edit_text(f"Текущая ставка: {new_bid} от @{user['username']}", reply_markup=auction_kb(auction_id, new_bid, auction["bid_step"]))
        await call.answer()  # Acknowledge the callback
    except Exception as e:
        print(f"Ошибка обработки ставки: {e}")
        await call.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)


async def check_auctions():
    while True:
        await asyncio.sleep(10)  # Проверяем каждые 10 секунд
        expired_auctions = await db.get_expired_auctions()
        for auction in expired_auctions:
            winner = await db.get_highest_bidder(auction["id"])
            try:
                if winner:
                    await bot.send_message(winner["user_id"], f"Поздравляем, вы выиграли аукцион {auction['title']} за {winner['bid_amount']}!")
                    await bot.send_message(channel_id, f"Победитель аукциона {auction['title']}: @{winner['username']} ({winner['first_name']} {winner['last_name']}) - {winner['bid_amount']}")
                else:
                    await bot.send_message(channel_id, f"Аукцион {auction['title']} не состоялся, ставок не было.")
                await db.close_auction(auction["id"])
            except Exception as e:
                print(f"Ошибка завершения аукциона: {e}")

async def main():
    print("Starting bot...")
    await db.connect()
    dp = Dispatcher()
    dp.include_router(router)
    asyncio.create_task(check_auctions())
    try:
        await dp.start_polling(bot)
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())