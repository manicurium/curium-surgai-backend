from rest_framework import serializers
from curium_surgai_backend.user.models import User

class RegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)

    class Meta:
        model = User
        fields = ["fname", "lname", "email_id", "password", "password2", "role_type"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def save(self):
        user = User(
            fname=self.validated_data["fname"],
            lname=self.validated_data["lname"],
            email_id=self.validated_data["email_id"],
            username=self.validated_data["email_id"],
            role_type=self.validated_data["role_type"],  # Ensure role_type is set
        )
        password = self.validated_data["password"]
        password2 = self.validated_data["password2"]

        if password != password2:
            raise serializers.ValidationError({"password": "Passwords must match."})
        user.set_password(password)
        user.save()
        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email_id", "fname", "lname", "role_type")  # Include role_type in the profile


class ProfilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "fname", "lname", "role_type")  # Include role_type
