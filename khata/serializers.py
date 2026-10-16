"""Khata contract — camelCase out, snake_case stays in DB. Money as JSON numbers."""

from rest_framework import serializers

from core.serializers import BhojBilashSerializer

from .models import Attendance, Expense, SalaryPayment, StaffMember


class StaffSerializer(BhojBilashSerializer):
    monthlySalary = serializers.SerializerMethodField()

    class Meta:
        model = StaffMember
        fields = ("_id", "name", "job", "phone", "monthlySalary", "active", "createdAt")

    def get_monthlySalary(self, obj) -> float:
        return float(obj.monthly_salary)


class AttendanceSerializer(BhojBilashSerializer):
    staffId = serializers.CharField(source="staff_id", read_only=True)
    inTime = serializers.CharField(source="in_time", read_only=True)
    outTime = serializers.CharField(source="out_time", read_only=True)

    class Meta:
        model = Attendance
        fields = ("_id", "staffId", "date", "status", "inTime", "outTime", "note", "createdAt")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["date"] = str(instance.date)
        return data


class ExpenseSerializer(BhojBilashSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = ("_id", "date", "category", "note", "amount", "by", "createdAt")

    def get_amount(self, obj) -> float:
        return float(obj.amount)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["date"] = str(instance.date)
        return data


class SalaryPaymentSerializer(BhojBilashSerializer):
    staffId = serializers.CharField(source="staff_id", read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = SalaryPayment
        fields = ("_id", "staffId", "month", "amount", "note", "date", "createdAt")

    def get_amount(self, obj) -> float:
        return float(obj.amount)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["date"] = str(instance.date)
        return data
