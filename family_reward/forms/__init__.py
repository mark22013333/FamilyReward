"""WTForms 表單定義。

前端的 required / pattern 只是為了 UX，
真正的安全驗證一律在這裡與 Service 層執行（不能只依賴 JavaScript）。
"""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
)

from ..models import (
    AVATAR_CHOICES,
    REPEAT_TYPE_LABELS,
    TASK_CATEGORY_LABELS,
    THEME_LABELS,
)
from ..utils.timezone import WEEKDAY_CODE_ZH, WEEKDAY_CODES


class AdminLoginForm(FlaskForm):
    username = StringField(
        "帳號",
        validators=[DataRequired(message="請輸入帳號"), Length(max=50)],
    )
    password = PasswordField(
        "密碼",
        validators=[DataRequired(message="請輸入密碼"), Length(max=200)],
    )
    submit = SubmitField("登入")


class ChildPinForm(FlaskForm):
    """小孩 PIN 登入。長度在 route 依 config 動態檢查。"""

    pin = StringField(
        "PIN",
        validators=[
            DataRequired(message="請輸入密碼數字"),
            Regexp(r"^\d{3,8}$", message="PIN 只能是數字"),
        ],
    )
    submit = SubmitField("開始冒險")


class ChangeUsernameForm(FlaskForm):
    """修改管理者帳號。需要輸入目前密碼確認身分。"""

    new_username = StringField(
        "新的帳號",
        validators=[
            DataRequired(message="請輸入新的帳號"),
            Length(min=3, max=50, message="帳號長度必須介於 3 ~ 50 個字元"),
            Regexp(
                r"^[A-Za-z0-9._-]+$",
                message="帳號只能使用英文字母、數字，以及 . _ - 這三種符號",
            ),
        ],
    )
    current_password = PasswordField(
        "目前的密碼", validators=[DataRequired(message="請輸入目前的密碼確認身分")]
    )
    submit = SubmitField("修改帳號")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "目前的密碼", validators=[DataRequired(message="請輸入目前的密碼")]
    )
    new_password = PasswordField(
        "新密碼",
        validators=[
            DataRequired(message="請輸入新密碼"),
            Length(min=8, max=200, message="新密碼至少 8 個字元"),
        ],
    )
    confirm_password = PasswordField(
        "再輸入一次新密碼", validators=[DataRequired(message="請再輸入一次新密碼")]
    )
    submit = SubmitField("修改密碼")


class PointsPerCardForm(FlaskForm):
    """集點卡設定。

    上限刻意不設太高 —— 集點卡是給小孩看的，設成 9999 等於永遠集不滿。
    """

    points_per_card = IntegerField(
        "幾點集滿一張集點卡",
        validators=[
            InputRequired(message="請填寫幾點集滿一張集點卡"),
            NumberRange(min=1, max=100, message="必須介於 1 ~ 100 點"),
        ],
        default=10,
    )
    submit = SubmitField("儲存集點卡設定")


class ChildForm(FlaskForm):
    name = StringField(
        "名字",
        validators=[DataRequired(message="請填寫名字"), Length(min=1, max=50)],
    )
    nickname = StringField("暱稱（選填）", validators=[Optional(), Length(max=50)])
    avatar = SelectField(
        "頭像",
        choices=[(emoji, emoji) for emoji in AVATAR_CHOICES],
        default="🐼",
        validators=[DataRequired()],
    )
    theme = SelectField(
        "主題色",
        choices=[(code, label) for code, label in THEME_LABELS.items()],
        default="SUNNY",
        validators=[DataRequired()],
    )
    birthday = DateField("生日（選填）", validators=[Optional()])
    pin = StringField(
        "PIN（4 位數字）",
        validators=[Optional(), Regexp(r"^\d{3,8}$", message="PIN 只能是數字")],
    )
    active = BooleanField("啟用中", default=True)
    submit = SubmitField("儲存")


class TaskForm(FlaskForm):
    title = StringField(
        "任務名稱",
        validators=[DataRequired(message="請填寫任務名稱"), Length(min=1, max=100)],
    )
    icon = StringField("圖示 Emoji", validators=[Optional(), Length(max=8)], default="⭐")
    description = TextAreaField("說明（選填）", validators=[Optional(), Length(max=500)])
    category = SelectField(
        "分類",
        choices=[(code, label) for code, label in TASK_CATEGORY_LABELS.items()],
        default="OTHER",
    )
    points = IntegerField(
        "點數",
        validators=[
            InputRequired(message="請填寫點數"),
            NumberRange(min=1, max=100, message="點數必須介於 1 ~ 100"),
        ],
        default=1,
    )
    required = BooleanField("列為必做任務（計入連續達成）", default=False)
    repeat_type = SelectField(
        "重複方式",
        choices=[(code, label) for code, label in REPEAT_TYPE_LABELS.items()],
        default="DAILY",
    )
    weekdays = SelectMultipleField(
        "星期",
        choices=[(code, WEEKDAY_CODE_ZH[code]) for code in WEEKDAY_CODES],
        validators=[Optional()],
    )
    child_ids = SelectMultipleField("指派給", coerce=int, validators=[Optional()])
    start_date = DateField("開始日期（選填）", validators=[Optional()])
    end_date = DateField("結束日期（選填）", validators=[Optional()])
    active = BooleanField("啟用中", default=True)
    submit = SubmitField("儲存")


class RewardForm(FlaskForm):
    name = StringField(
        "禮物名稱",
        validators=[DataRequired(message="請填寫禮物名稱"), Length(min=1, max=100)],
    )
    icon = StringField("圖示 Emoji", validators=[Optional(), Length(max=8)], default="🎁")
    description = TextAreaField("說明（選填）", validators=[Optional(), Length(max=500)])
    points_required = IntegerField(
        "需要點數",
        validators=[
            InputRequired(message="請填寫需要的點數"),
            NumberRange(min=1, max=10000, message="需要點數必須介於 1 ~ 10000"),
        ],
        default=10,
    )
    quantity = IntegerField(
        "數量（留空代表無限）",
        validators=[Optional(), NumberRange(min=0, message="數量不能是負數")],
    )
    active = BooleanField("啟用中", default=True)
    submit = SubmitField("儲存")


class PointAdjustmentForm(FlaskForm):
    child_id = SelectField("小朋友", coerce=int, validators=[InputRequired()])
    points = IntegerField(
        "調整點數（正數增加、負數減少）",
        validators=[
            InputRequired(message="請填寫要調整的點數"),
            NumberRange(min=-1000, max=1000, message="一次最多調整 1000 點"),
        ],
    )
    reason = StringField(
        "理由",
        validators=[DataRequired(message="請填寫調整理由"), Length(min=1, max=200)],
    )
    submit = SubmitField("送出調整")


class RejectForm(FlaskForm):
    """退回任務時填寫的友善提醒。"""

    reason = StringField("想跟小朋友說的話", validators=[Optional(), Length(max=200)])
    submit = SubmitField("還要再努力一下")


class ConfirmForm(FlaskForm):
    """只需要 CSRF 保護的簡單確認表單（批准 / 停用 / 備份等）。"""

    submit = SubmitField("確認")
