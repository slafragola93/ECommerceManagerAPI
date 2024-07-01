from fastapi import APIRouter
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError

from src import Role
from src.schemas.user_schema import *
from src.services.auth import *

load_dotenv()

router = APIRouter(
    prefix='/api/v1/auth',
    tags=['Authentication'],
)

ALHORITHM = "HS256"
SECRET_KEY = os.environ.get("SECRET_KEY")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, us: UserSchema):
    """
        Crea un nuovo utente nel sistema.

        Utilizza le informazioni fornite per creare un record utente nel database. Gestisce automaticamente
        la cifratura della password. In caso di username o email già presenti, restituisce un errore 400. Per altri
        errori interni, restituisce un errore 500.

        Parameters:
        - db: db_dependency - Dipendenza del database per eseguire operazioni di inserimento.
        - us: UserSchema - Oggetto contenente i dati dell'utente da registrare.

        Returns:
        - User: L'utente appena creato, se la registrazione è avvenuta con successo.

        Raises:
        - HTTPException: Con status code 400 se l'utente esiste già, con status code 500 per altri errori interni.
    """
    try:
        user = User(
            username=us.username,
            email=us.email,
            firstname=us.firstname,
            lastname=us.lastname,
            password=bcrypt_context.hash(us.password)
        )

        if us.roles:
            role_ids = [role.id_role for role in us.roles]
            roles = db.query(Role).filter(Role.id_role.in_(role_ids)).all()
            user.roles = roles
        else:
            # Assegna il ruolo predefinito "user"
            default_role = db.query(Role).filter(Role.name == "USER").first()
            if not default_role:
                raise HTTPException(status_code=500, detail="Default role 'user' not found")
            user.roles.append(default_role)


        db.add(user)
        db.commit()
        return user
    except IntegrityError:
        # Log errore generico
        db.rollback()
        raise HTTPException(status_code=400, detail="Esiste già un utente con questi dati.")
    except Exception as e:
        # Log dell'errore generico
        print(f"Errore durante la creazione dell'utente: {e}")
        # Solleva un'altra eccezione HTTP
        raise HTTPException(status_code=500, detail=f"Errore interno del server: {e}")


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def get_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                    db: db_dependency):
    """
        Autentica un utente e restituisce un token JWT per l'accesso.

        Verifica le credenziali fornite tramite form_data. In caso di successo, genera un token di accesso JWT
        valido per 30 giorni e lo restituisce insieme al tipo di token. Se le credenziali non sono valide,
        restituisce un errore 401.

        Parameters:
        - username
        - password

        Returns:
        - dict: Un dizionario contenente il token di accesso, il tipo di token, username e scadenza

        Raises:
        - HTTPException: Con status code 401 se le credenziali non sono valide.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    expires_delta = timedelta(days=30)
    expires_at = datetime.utcnow() + expires_delta

    # Login OK, creazione JWT token
    token = create_access_token(username=user.username,
                                user_id=user.id_user,
                                expires_delta=expires_delta,
                                roles=user.roles
                                )

    return {
        "access_token": token,
        "token_type": "bearer",
        "current_user": form_data.username,
        "expires_at": expires_at
    }

# TODO: Sistema di recupero password tramite link via mail
