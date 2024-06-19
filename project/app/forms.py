from django import forms
from django.contrib.auth.forms import UserCreationForm,AuthenticationForm,PasswordChangeForm
from django.contrib.auth.models import User
from django.forms.widgets import TextInput,PasswordInput
from .models import Customer

# class RegisterForm(UserCreationForm):
    
#     class Meta:
#         model = User
#         fields=['first_name','last_name','phone','email','username', 'password1', 'password2']
        
        
class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=TextInput(attrs={'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=PasswordInput(attrs={'placeholder': 'Password'})
    )
    
class RecordForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields=['first_name','last_name','email','phone']
        
class ChangePassword(PasswordChangeForm):
    class Meta:
        model = User
        fields = ['old_password', 'new_password1', 'new_password2']
class UpdateForm(forms.ModelForm):
    class Meta:
        model= Customer
        fields=['first_name','last_name','email','phone']
