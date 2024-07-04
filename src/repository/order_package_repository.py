from sqlalchemy.orm import Session
from .. import OrderPackageSchema, OrderPackageResponseSchema
from ..models.order_package import OrderPackage


class OrderPackageRepository:

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_by_id(self, _id: int) -> OrderPackageResponseSchema:
        return self.session.query(OrderPackage).filter(OrderPackage.id_order_package == _id).first()

    def create(self, data: OrderPackageSchema):

        order_package = OrderPackage(**data.model_dump())

        self.session.add(order_package)
        self.session.commit()
        self.session.refresh(order_package)

    def update(self,
               edited_order_package: OrderPackage,
               data: OrderPackageSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_order_package, key) and value is not None:
                setattr(edited_order_package, key, value)

        self.session.add(edited_order_package)
        self.session.commit()

    def delete(self, order_package: OrderPackage) -> bool:
        self.session.delete(order_package)
        self.session.commit()

        return True
