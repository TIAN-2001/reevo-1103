import logging
from datetime import datetime, timedelta
import time

# --- Configure Logging ---
# Sets up logging to print info-level messages with a timestamp
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Item:
    """
    Represents a single item in the inventory.
    """
    def __init__(self, item_id, name, category, stock, unit_price, last_restock_date, reorder_threshold):
        self.item_id = item_id
        self.name = name
        self.category = category
        self.stock = stock
        self.unit_price = unit_price
        self.last_restock_date = datetime.strptime(last_restock_date, '%Y-%m-%d').date()
        self.reorder_threshold = reorder_threshold
        
    def adjust_stock(self, amount: int):
        """
        Adjusts the stock level. Raises ValueError if stock would go negative.
        """
        if self.stock + amount < 0:
            raise ValueError(
                f"Cannot adjust stock for {self.item_id} by {amount}. "
                f"Only {self.stock} units are available."
            )
        self.stock += amount
        logging.info(f"Stock for {self.item_id} ({self.name}) adjusted by {amount}. New stock: {self.stock}")

    def __repr__(self):
        """
        Provides a clean string representation for the item.
        """
        return (
            f"Item(ID: {self.item_id}, Name: {self.name}, Stock: {self.stock}, "
            f"Price: ${self.unit_price:.2f}, Last Restock: {self.last_restock_date})"
        )

class Offer:
    """
    Represents a batch of inventory up for bidding.
    """
    def __init__(self, offer_id, item_id, quantity, end_time):
        self.offer_id = offer_id
        self.item_id = item_id
        self.quantity = quantity
        self.end_time = end_time
        self.bids = {}  # {merchant_id: bid_amount}
        self.status = "active" # active, completed, cancelled
        self.winner = None
        self.winning_bid = 0

    def add_bid(self, merchant_id, amount):
        """
        Adds or updates a bid from a merchant.
        """
        if self.status != "active":
            logging.warning(f"Cannot accept bid. Offer {self.offer_id} is not active.")
            return False
            
        if datetime.now() > self.end_time:
            logging.warning(
                f"Cannot accept bid from {merchant_id}. "
                f"Bidding window for {self.offer_id} has closed."
            )
            return False

        # Allow merchants to update their bid
        if merchant_id in self.bids and self.bids[merchant_id] >= amount:
            logging.info(f"New bid from {merchant_id} of ${amount} is not higher than their previous bid.")
            return False

        self.bids[merchant_id] = amount
        logging.info(f"New highest bid for {self.offer_id} from {merchant_id}: ${amount:.2f}")
        return True

    def get_highest_bid(self):
        """
        Finds the highest bid and the corresponding merchant.
        """
        if not self.bids:
            return None, 0
        
        # Sort items by bid amount (value) in descending order
        highest_bidder = max(self.bids.items(), key=lambda item: item[1])
        return highest_bidder # (merchant_id, amount)

    def __repr__(self):
        return (
            f"Offer(ID: {self.offer_id}, Item: {self.item_id}, Qty: {self.quantity}, "
            f"Status: {self.status}, End: {self.end_time}, "
            f"Highest Bid: ${self.winning_bid:.2f} by {self.winner}, Bids: {len(self.bids)})"
        )

class InventoryManager:
    """
    Main backend system to manage inventory, sales, and bidding.
    """
    def __init__(self):
        self.inventory = {} # {item_id: Item object}
        self.offers = {}    # {offer_id: Offer object}
        self.next_offer_id = 1
        self._load_initial_inventory()

    def _load_initial_inventory(self):
        """
        Populates the inventory with the fixed set of items.
        """
        items = [
            Item("TS-A", "T-Shirt style A", "Clothing", 50, 20.00, "2025-09-01", 10),
            Item("TS-B", "T-Shirt style B", "Clothing", 20, 25.00, "2025-09-15", 5),
            Item("SH-C", "Men's shorts - Cargo", "Clothing", 65, 25.00, "2025-09-15", 5),
        ]
        for item in items:
            self.inventory[item.item_id] = item
        logging.info("Initial inventory loaded.")

    # --- Requirement 1: View Item Details ---
    def view_item_details(self, item_id: str):
        """
        Prints the details for a specific item.
        """
        item = self.inventory.get(item_id)
        if item:
            print(
                f"Details for {item.item_id} ({item.name}):\n"
                f"  - Current Stock: {item.stock} units\n"
                f"  - Unit Price: ${item.unit_price:.2f}\n"
                f"  - Last Restock: {item.last_restock_date}"
            )
        else:
            logging.error(f"Item {item_id} not found.")

    # --- Requirement 2: Update Stock ---
    def update_stock(self, item_id: str, adjustment_amount: int):
        """
        Manually adjusts stock for an item (e.g., damaged goods).
        """
        item = self.inventory.get(item_id)
        if not item:
            logging.error(f"Item {item_id} not found for stock update.")
            return

        try:
            item.adjust_stock(adjustment_amount)
            logging.info(f"Manual stock adjustment for {item_id} complete.")
        except ValueError as e:
            logging.error(f"Stock update failed for {item_id}: {e}")

    # --- Requirement 3: Create New Offer ---
    def create_new_offer(self, item_id: str, quantity: int, end_time: datetime) -> str | None:
        """
        Creates a new bidding offer, earmarking inventory.
        """
        item = self.inventory.get(item_id)
        if not item:
            logging.error(f"Item {item_id} not found. Cannot create offer.")
            return None

        try:
            # Earmark the inventory by removing it from main stock
            item.adjust_stock(-quantity)
            
            offer_id = f"OFFER-{self.next_offer_id}"
            self.next_offer_id += 1
            
            offer = Offer(offer_id, item_id, quantity, end_time)
            self.offers[offer_id] = offer
            
            logging.info(f"Created {offer_id} for {quantity} units of {item.name}. Bidding ends {end_time}.")
            return offer_id
            
        except ValueError as e:
            # This triggers if not enough stock is available
            logging.error(f"Cannot create offer: {e}")
            return None

    # --- Requirement 4: Track Bids ---
    def track_bid(self, offer_id: str, merchant_id: str, amount: float):
        """
        Records a bid from a merchant for a specific offer.
        """
        offer = self.offers.get(offer_id)
        if not offer:
            logging.error(f"Offer {offer_id} not found. Cannot track bid.")
            return
            
        offer.add_bid(merchant_id, amount)

    # --- Requirement 5: Complete a Bid ---
    def complete_bid(self, offer_id: str):
        """
        Completes an offer, finds the winner, and finalizes the sale.
        If no bids, returns stock.
        """
        offer = self.offers.get(offer_id)
        if not offer:
            logging.error(f"Offer {offer_id} not found. Cannot complete.")
            return
        
        if offer.status != "active":
            logging.error(f"Offer {offer_id} is already completed or cancelled.")
            return

        if datetime.now() <= offer.end_time:
            logging.warning(
                f"Bidding for {offer_id} is still active. "
                f"Window closes at {offer.end_time}."
            )
            # In a real system, you might prevent this, but for testing
            # we'll allow early completion if needed.
            # For this problem, we will enforce waiting.
            return

        winner_id, winning_bid = offer.get_highest_bid()
        
        if winner_id:
            offer.status = "completed"
            offer.winner = winner_id
            offer.winning_bid = winning_bid
            logging.info(
                f"Offer {offer_id} completed. Sold {offer.quantity} units of {offer.item_id} "
                f"to {winner_id} for ${winning_bid:.2f}."
            )
            # Inventory was already removed, so the sale is just recorded.
        else:
            logging.info(f"Offer {offer_id} completed with no bids.")
            # Return the earmarked inventory to the main stock
            item = self.inventory.get(offer.item_id)
            if item:
                try:
                    item.adjust_stock(offer.quantity)
                    logging.info(f"Returned {offer.quantity} units of {offer.item_id} to stock.")
                except ValueError as e:
                    # This should never happen, but good to log
                    logging.critical(f"Error returning stock: {e}")
            offer.status = "completed"

    # --- Requirement 6: One-Off Orders ---
    def process_one_off_order(self, item_id: str, quantity: int) -> float | None:
        """
        Processes a simple, direct-to-consumer order.
        """
        item = self.inventory.get(item_id)
        if not item:
            logging.error(f"Item {item_id} not found. Cannot process order.")
            return None
            
        try:
            # This will raise ValueError if stock is insufficient
            item.adjust_stock(-quantity)
            
            total_price = item.unit_price * quantity
            logging.info(
                f"Processed one-off order for {quantity} units of {item.item_id}. "
                f"Total: ${total_price:.2f}"
            )
            return total_price
            
        except ValueError as e:
            logging.error(f"Cannot process one-off order: {e}")
            return None


# --- Main execution block for testing ---
if __name__ == "__main__":
    
    manager = InventoryManager()

    print("\n" + "="*50)
    print("RUNNING INVENTORY & BIDDING SYSTEM TESTS")
    print("="*50)

    # --- Test for Requirement 1: View item details ---
    print("\n--- Test 1: View Item Details ---")
    manager.view_item_details('TS-A')
    manager.view_item_details('NON-EXISTENT-ITEM') # Test failure case

    # --- Test for Requirement 2: Update stock ---
    print("\n--- Test 2: Update Stock (Manual Adjustment) ---")
    logging.info("Recording 5 damaged units of 'TS-A'.")
    manager.update_stock('TS-A', -5)
    manager.view_item_details('TS-A') # Should show 45 units
    manager.update_stock('TS-A', -1000) # Test insufficient stock

    # --- Test for Requirement 6: One-off orders ---
    print("\n--- Test 6: Process One-Off Order ---")
    logging.info("Selling 2 units of 'TS-B' to a regular customer.")
    manager.process_one_off_order('TS-B', 2)
    manager.view_item_details('TS-B') # Should show 18 units
    manager.process_one_off_order('TS-B', 100) # Test insufficient stock

    # --- Test for Requirement 3: Create a new offer ---
    print("\n--- Test 3: Create New Offer ---")
    # Set a short bidding window for testing
    bid_end_time = datetime.now() + timedelta(seconds=5)
    logging.info(f"Creating an offer for 20 units of 'TS-A'. Bidding ends in 5 seconds.")
    offer_id_1 = manager.create_new_offer('TS-A', 20, bid_end_time)
    print(f"Created Offer ID: {offer_id_1}")
    manager.view_item_details('TS-A') # Stock should be 25 (45 - 20)
    manager.create_new_offer('TS-A', 1000, bid_end_time) # Test insufficient stock

    # --- Test for Requirement 4: Tracking bids ---
    print("\n--- Test 4: Track Bids ---")
    start_price = manager.inventory['TS-A'].unit_price * 20 # 20 * $20 = $400
    logging.info(f"Base price for {offer_id_1} is ${start_price:.2f}")
    manager.track_bid(offer_id_1, 'Merchant-Alpha', 450.00)
    manager.track_bid(offer_id_1, 'Merchant-Beta', 500.00)
    manager.track_bid(offer_id_1, 'Merchant-Alpha', 510.00) # Alpha updates their bid
    print(manager.offers[offer_id_1])

    # --- Test for Requirement 5: Completing a bid ---
    print("\n--- Test 5: Complete Bid (with winner) ---")
    logging.info("Attempting to complete bid early (should fail)...")
    manager.complete_bid(offer_id_1) # Should fail as window is open
    
    logging.info("Waiting 6 seconds for bidding window to close...")
    time.sleep(6)
    
    logging.info("Window closed. Attempting to track a late bid (should fail)...")
    manager.track_bid(offer_id_1, 'Merchant-Gamma', 520.00) # Should fail
    
    logging.info("Completing the bid...")
    manager.complete_bid(offer_id_1) # Should now succeed
    print(manager.offers[offer_id_1])
    manager.view_item_details('TS-A') # Stock should remain 25

    # --- Test for Requirement 5 (No Bids Case) ---
    print("\n--- Test 5b: Complete Bid (No Bids) ---")
    bid_end_time_2 = datetime.now() + timedelta(seconds=2)
    logging.info(f"Creating offer for 5 units of 'TS-B'. Bidding ends in 2 seconds.")
    offer_id_2 = manager.create_new_offer('TS-B', 5, bid_end_time_2)
    manager.view_item_details('TS-B') # Stock should be 13 (18 - 5)
    
    logging.info("Waiting 3 seconds for window to close (no bids will be placed)...")
    time.sleep(3)
    
    logging.info("Completing the bid...")
    manager.complete_bid(offer_id_2)
    print(manager.offers[offer_id_2])
    
    logging.info("Verifying stock was returned...")
    manager.view_item_details('TS-B') # Stock should be 18 again (13 + 5)

    print("\n" + "="*50)
    print("ALL TESTS COMPLETE")
    print("="*50)
