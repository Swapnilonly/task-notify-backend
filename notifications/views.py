from django.shortcuts import render

# Create your views here.


# Should NOT directly create notifications inside task views.
#
# Correct flow:
#
# Task Created
#    ↓
# Task Service
#    ↓
# Notification Service Triggered