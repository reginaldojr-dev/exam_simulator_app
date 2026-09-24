public class InventoryApp { public static void main(String[] args){ Inventory inv = new Inventory(); for(String a: args) inv.add(Integer.parseInt(a)); System.out.println(inv.total()); } }
