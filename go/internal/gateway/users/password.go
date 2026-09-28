package users

import "golang.org/x/crypto/bcrypt"

const bcryptCost = 12

// HashPassword returns a bcrypt hash of password.
func HashPassword(password string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcryptCost)
	if err != nil {
		return "", err
	}
	return string(hash), nil
}

// CheckPassword returns nil when password matches hash.
func CheckPassword(hash, password string) error {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
}
