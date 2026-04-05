"""Barcha FSM holatlar — bot jarayonlari uchun."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Qo'shimcha admin ro'yxatdan o'tish."""
    waiting_full_name = State()
    waiting_phone = State()


class OrderStates(StatesGroup):
    """Yangi buyurtma yaratish jarayoni."""
    waiting_client_name = State()
    waiting_client_phone = State()
    waiting_vehicle_model = State()
    waiting_custom_vehicle_model = State()
    waiting_vin = State()
    waiting_services = State()
    waiting_total_amount = State()
    waiting_van_height = State()
    waiting_group = State()
    waiting_confirm = State()


class CatalogStates(StatesGroup):
    """Katalog elementlarini boshqarish."""
    waiting_add_name = State()
    waiting_add_master_phone = State()
    waiting_edit_name = State()
    waiting_edit_sort_order = State()
    waiting_edit_master_phone = State()


class SearchStates(StatesGroup):
    """Mijoz qidiruvi."""
    waiting_query = State()
    waiting_output_format = State()


class MasterGroupStates(StatesGroup):
    """Usta guruhlarini boshqarish."""
    waiting_group_name = State()
    waiting_group_rename = State()


class MasterStates(StatesGroup):
    """Usta interfeysidagi holatlar."""
    waiting_access_code = State()
    waiting_completion_video = State()


class OrderManageStates(StatesGroup):
    """Buyurtmani tahrirlash / bekor qilish."""
    waiting_edit_amount = State()
    waiting_comment = State()


class StatisticsStates(StatesGroup):
    """Statistika filtrlash."""
    waiting_custom_date = State()


class LicenseStates(StatesGroup):
    """Litsenziya ro'yxati va qidiruvi."""
    waiting_vin = State()
    waiting_client_name = State()
    waiting_client_phone = State()


class LicenseSearchStates(StatesGroup):
    waiting_search_vin = State()
